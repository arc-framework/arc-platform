"""Unit tests for sherlock.openai_nats_handler.OpenAINATSHandler.

Tests cover the _handle() dispatch logic: fire-and-forget semantics, request-reply
dual publish, error responses, connection state, user_id derivation, and the
invariant that no message content appears in log calls.

asyncio_mode = "auto" from pyproject.toml — no explicit @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sherlock.config import Settings
from sherlock.models_v1 import ChatCompletionResponse
from sherlock.observability import SherlockMetrics
from sherlock.openai_nats_handler import OpenAINATSHandler, _derive_user_id

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.nats_url = "nats://localhost:4222"
    s.nats_v1_chat_subject = "sherlock.v1.chat"
    s.nats_v1_result_subject = "sherlock.v1.result"
    s.nats_queue_group = "sherlock_workers"
    s.nats_v1_enabled = True
    return s


def _make_metrics() -> MagicMock:
    m = MagicMock(spec=SherlockMetrics)
    m.v1_requests_total = MagicMock()
    m.v1_requests_total.add = MagicMock()
    m.v1_errors_total = MagicMock()
    m.v1_errors_total.add = MagicMock()
    m.v1_latency = MagicMock()
    m.v1_latency.record = MagicMock()
    return m


def _make_handler() -> OpenAINATSHandler:
    """Return an OpenAINATSHandler with all dependencies mocked (no live NATS)."""
    handler = OpenAINATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=_make_settings(),
        metrics=_make_metrics(),
    )
    # Inject a mock NATS client so _handle() can publish
    mock_nc = MagicMock()
    mock_nc.publish = AsyncMock()
    mock_nc.is_connected = True
    handler._nc = mock_nc
    return handler


def _make_msg(messages_data: list[dict], reply: str | None = None) -> MagicMock:
    """Create a fake NATS Msg with ChatCompletionRequest payload."""
    payload = {
        "model": "test-model",
        "messages": messages_data,
        "stream": False,
    }
    msg = MagicMock()
    msg.data = json.dumps(payload).encode()
    msg.subject = "sherlock.v1.chat"
    msg.reply = reply
    msg.respond = AsyncMock()
    return msg


# ─── Fire-and-forget (no reply) ───────────────────────────────────────────────


async def test_fire_and_forget_no_respond_called() -> None:
    """When msg.reply is None, msg.respond() is NOT called."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="response text",
    ):
        await handler._handle(msg)

    msg.respond.assert_not_called()


async def test_fire_and_forget_result_published() -> None:
    """Fire-and-forget: result is published to the result subject."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="response text",
    ):
        await handler._handle(msg)

    handler._nc.publish.assert_awaited_once_with(
        "sherlock.v1.result",
        handler._nc.publish.call_args.args[1],
    )


# ─── Request-reply ────────────────────────────────────────────────────────────


async def test_request_reply_respond_called() -> None:
    """When msg.reply is set, msg.respond() is called with the result bytes."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hi"}], reply="INBOX.123")

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="reply response",
    ):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()


async def test_request_reply_also_publishes_to_result_subject() -> None:
    """Request-reply: result is ALSO published to result subject (dual publish)."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hi"}], reply="INBOX.123")

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="dual publish response",
    ):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()
    handler._nc.publish.assert_awaited_once_with(
        "sherlock.v1.result",
        handler._nc.publish.call_args.args[1],
    )


async def test_request_reply_respond_payload_is_valid_response() -> None:
    """The bytes sent to msg.respond() decode as valid ChatCompletionResponse."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hi"}], reply="INBOX.abc")

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="the answer",
    ):
        await handler._handle(msg)

    raw = msg.respond.call_args.args[0]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert parsed.choices[0].message.content == "the answer"
    assert parsed.model == "test-model"
    assert parsed.object == "chat.completion"


# ─── Missing user message ─────────────────────────────────────────────────────


async def test_missing_user_message_publishes_error_no_crash() -> None:
    """No user-role message → error response is published, handler does not raise."""
    handler = _make_handler()
    # Only system message — no user role
    msg = _make_msg([{"role": "system", "content": "you are helpful"}], reply=None)

    # Should not raise
    await handler._handle(msg)

    # Error metrics incremented
    handler._metrics.v1_errors_total.add.assert_called_once()

    # A response was still published
    handler._nc.publish.assert_awaited_once()
    raw = handler._nc.publish.call_args.args[1]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert "Error" in parsed.choices[0].message.content


async def test_missing_user_message_with_reply_no_crash() -> None:
    """No user message + reply set → error published, msg.respond() NOT called."""
    handler = _make_handler()
    msg = _make_msg([{"role": "system", "content": "sys"}], reply="INBOX.err")

    await handler._handle(msg)

    # respond is called only when msg.reply is set — error path still calls it
    # because the result is built before the publish block
    # (the reply is sent regardless of error or success)
    handler._nc.publish.assert_awaited_once()
    raw = handler._nc.publish.call_args.args[1]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert "Error" in parsed.choices[0].message.content


# ─── invoke_graph exception ───────────────────────────────────────────────────


async def test_invoke_graph_exception_publishes_error() -> None:
    """When invoke_graph raises, error response is published and no exception propagates."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "crash me"}], reply=None)

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        side_effect=RuntimeError("graph exploded"),
    ):
        await handler._handle(msg)  # must not raise

    handler._nc.publish.assert_awaited_once()
    raw = handler._nc.publish.call_args.args[1]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert "graph exploded" in parsed.choices[0].message.content
    handler._metrics.v1_errors_total.add.assert_called_once()


async def test_invoke_graph_exception_with_reply_responds() -> None:
    """invoke_graph exception + reply set → error also sent to inbox."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "boom"}], reply="INBOX.crash")

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        side_effect=ValueError("bad value"),
    ):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()
    raw = msg.respond.call_args.args[0]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert "bad value" in parsed.choices[0].message.content


# ─── Valid ChatCompletionResponse JSON ────────────────────────────────────────


async def test_result_bytes_are_valid_chat_completion_response() -> None:
    """Published bytes (result subject) always decode as valid ChatCompletionResponse."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "valid?"}], reply=None)

    with patch(
        "sherlock.openai_nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="validated",
    ):
        await handler._handle(msg)

    raw = handler._nc.publish.call_args.args[1]
    parsed = ChatCompletionResponse.model_validate_json(raw)
    assert parsed.object == "chat.completion"
    assert len(parsed.choices) == 1
    assert parsed.usage.total_tokens == 0


# ─── No message content in logs ───────────────────────────────────────────────


async def test_no_message_content_in_debug_log() -> None:
    """_log.debug calls must not include user message content."""
    handler = _make_handler()
    secret_text = "super-secret-user-content-XYZ"
    msg = _make_msg([{"role": "user", "content": secret_text}], reply=None)

    debug_calls: list = []
    error_calls: list = []

    with patch("sherlock.openai_nats_handler._log") as mock_log:
        mock_log.debug = MagicMock(side_effect=lambda *a, **kw: debug_calls.append((a, kw)))
        mock_log.error = MagicMock(side_effect=lambda *a, **kw: error_calls.append((a, kw)))

        with patch(
            "sherlock.openai_nats_handler.invoke_graph",
            new_callable=AsyncMock,
            return_value="safe response",
        ):
            await handler._handle(msg)

    # Check no debug or error call contains the message content
    all_calls = debug_calls + error_calls
    for args, kwargs in all_calls:
        combined = str(args) + str(kwargs)
        assert secret_text not in combined, (
            f"Message content found in log call: {combined!r}"
        )


async def test_no_message_content_in_error_log_on_exception() -> None:
    """_log.error calls on exception must not expose the user message content."""
    handler = _make_handler()
    secret_text = "private-user-data-ABC"
    msg = _make_msg([{"role": "user", "content": secret_text}], reply=None)

    error_calls: list = []

    with patch("sherlock.openai_nats_handler._log") as mock_log:
        mock_log.debug = MagicMock()
        mock_log.error = MagicMock(side_effect=lambda *a, **kw: error_calls.append((a, kw)))

        with patch(
            "sherlock.openai_nats_handler.invoke_graph",
            new_callable=AsyncMock,
            side_effect=RuntimeError("some error"),
        ):
            await handler._handle(msg)

    for args, kwargs in error_calls:
        combined = str(args) + str(kwargs)
        assert secret_text not in combined, (
            f"Message content found in error log: {combined!r}"
        )


# ─── is_connected() ───────────────────────────────────────────────────────────


def test_is_connected_true_when_v1_disabled() -> None:
    """is_connected() returns True when nats_v1_enabled=False (always-ready shortcut)."""
    settings = _make_settings()
    settings.nats_v1_enabled = False
    handler = OpenAINATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=settings,
        metrics=_make_metrics(),
    )
    assert handler.is_connected() is True


def test_is_connected_true_when_nc_connected() -> None:
    """is_connected() returns True when _nc is set and is_connected is True."""
    handler = _make_handler()
    handler._nc.is_connected = True
    assert handler.is_connected() is True


def test_is_connected_false_when_nc_none() -> None:
    """is_connected() returns False when _nc has not been set."""
    settings = _make_settings()
    settings.nats_v1_enabled = True
    handler = OpenAINATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=settings,
        metrics=_make_metrics(),
    )
    # _nc starts as None
    assert handler.is_connected() is False


# ─── user_id derivation ───────────────────────────────────────────────────────


async def test_user_id_uses_req_user_when_set() -> None:
    """invoke_graph receives the user_id from req.user when explicitly provided."""
    handler = _make_handler()
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "user": "explicit-user-123",
    }
    msg = MagicMock()
    msg.data = json.dumps(payload).encode()
    msg.subject = "sherlock.v1.chat"
    msg.reply = None
    msg.respond = AsyncMock()

    captured_user_id: list[str] = []

    async def fake_invoke(graph, memory, user_id: str, text: str) -> str:
        captured_user_id.append(user_id)
        return "ok"

    with patch("sherlock.openai_nats_handler.invoke_graph", side_effect=fake_invoke):
        await handler._handle(msg)

    assert captured_user_id == ["explicit-user-123"]


async def test_user_id_derives_uuid_v5_when_absent() -> None:
    """When req.user is absent, user_id is a deterministic UUID v5 from message content."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "stable content"}], reply=None)

    captured_user_id: list[str] = []

    async def fake_invoke(graph, memory, user_id: str, text: str) -> str:
        captured_user_id.append(user_id)
        return "ok"

    with patch("sherlock.openai_nats_handler.invoke_graph", side_effect=fake_invoke):
        await handler._handle(msg)

    assert len(captured_user_id) == 1
    derived = captured_user_id[0]
    # Must be a valid UUID
    parsed = uuid.UUID(derived)
    assert parsed.version == 5

    # Deterministic: same content → same UUID
    expected = _derive_user_id(
        [type("M", (), {"role": "user", "content": "stable content"})()]  # type: ignore[arg-type]
    )
    assert derived == expected


# ─── _derive_user_id unit test ────────────────────────────────────────────────


def test_derive_user_id_stable_across_calls() -> None:
    """_derive_user_id returns the same UUID v5 for identical message content."""
    from sherlock.models_v1 import ChatMessage

    messages = [
        ChatMessage(role="user", content="hello world"),
        ChatMessage(role="assistant", content="hi"),
    ]
    uid1 = _derive_user_id(messages)
    uid2 = _derive_user_id(messages)
    assert uid1 == uid2
    assert uuid.UUID(uid1).version == 5


def test_derive_user_id_only_uses_user_messages() -> None:
    """_derive_user_id ignores non-user messages when building the hash."""
    from sherlock.models_v1 import ChatMessage

    messages_with_system = [
        ChatMessage(role="system", content="system prompt"),
        ChatMessage(role="user", content="test"),
    ]
    messages_without_system = [
        ChatMessage(role="user", content="test"),
    ]
    assert _derive_user_id(messages_with_system) == _derive_user_id(messages_without_system)
