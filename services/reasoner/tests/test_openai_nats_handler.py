"""Unit tests for reasoner.openai_nats_handler.OpenAINATSHandler.

Tests cover the _handle() streaming dispatch: token chunks published to stream
subject, completion signal to result subject, TTFT recorded, error path, 
fire-and-forget vs request-reply, and user_id derivation.

asyncio_mode = "auto" from pyproject.toml — no explicit @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from reasoner.config import Settings
from reasoner.observability import SherlockMetrics
from reasoner.openai_nats_handler import OpenAINATSHandler, _derive_user_id

# ─── Async generator mocks ────────────────────────────────────────────────────


async def _mock_stream_chunks(*args, **kwargs):
    """Async generator yielding two token chunks."""
    yield "Hello"
    yield " world"


async def _mock_stream_empty(*args, **kwargs):
    """Async generator that yields nothing."""
    return
    yield  # make it a generator


async def _mock_stream_error(*args, **kwargs):
    """Async generator that raises immediately."""
    raise RuntimeError("stream failed")
    yield  # make it a generator


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.nats_url = "nats://localhost:4222"
    s.nats_v1_chat_subject = "reasoner.v1.chat"
    s.nats_v1_result_subject = "reasoner.v1.result"
    s.nats_queue_group = "reasoner_workers"
    s.nats_v1_enabled = True
    s.arc_nats_stream_prefix = "arc.reasoner.stream"
    s.arc_nats_result_subject = "arc.reasoner.result"
    s.arc_nats_error_subject = "arc.reasoner.error"
    return s


def _make_metrics() -> MagicMock:
    m = MagicMock(spec=SherlockMetrics)
    m.v1_requests_total = MagicMock()
    m.v1_requests_total.add = MagicMock()
    m.v1_errors_total = MagicMock()
    m.v1_errors_total.add = MagicMock()
    m.v1_latency = MagicMock()
    m.v1_latency.record = MagicMock()
    m.ttft_seconds = MagicMock()
    m.ttft_seconds.record = MagicMock()
    return m


def _make_handler() -> OpenAINATSHandler:
    """Return an OpenAINATSHandler with all dependencies mocked (no live NATS)."""
    handler = OpenAINATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=_make_settings(),
        metrics=_make_metrics(),
    )
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
    msg.subject = "reasoner.v1.chat"
    msg.reply = reply
    msg.respond = AsyncMock()
    return msg


# ─── Token streaming ──────────────────────────────────────────────────────────


async def test_token_chunks_published_to_stream_subject() -> None:
    """Each yielded chunk is published to arc.reasoner.stream.{request_id}."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    # Two chunk publishes + one arc result + one v1 result = 4 publishes total
    calls = handler._nc.publish.call_args_list
    stream_calls = [c for c in calls if c.args[0].startswith("arc.reasoner.stream.")]
    assert len(stream_calls) == 2

    chunks = [json.loads(c.args[1])["chunk"] for c in stream_calls]
    assert chunks == ["Hello", " world"]


async def test_completion_signal_published_to_arc_result() -> None:
    """Completion payload (done=True) is published to arc.reasoner.result."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    calls = handler._nc.publish.call_args_list
    result_calls = [c for c in calls if c.args[0] == "arc.reasoner.result"]
    assert len(result_calls) == 1

    payload = json.loads(result_calls[0].args[1])
    assert payload["done"] is True
    assert "request_id" in payload
    assert "ttft_ms" in payload
    assert "latency_ms" in payload


async def test_completion_also_published_to_legacy_v1_result() -> None:
    """Completion is also published to reasoner.v1.result for backward compat."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    calls = handler._nc.publish.call_args_list
    v1_result_calls = [c for c in calls if c.args[0] == "reasoner.v1.result"]
    assert len(v1_result_calls) == 1


async def test_ttft_recorded_on_first_token() -> None:
    """ttft_seconds is recorded exactly once, on the first yielded chunk."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    handler._metrics.ttft_seconds.record.assert_called_once()
    args = handler._metrics.ttft_seconds.record.call_args
    # First arg is seconds value — must be non-negative
    assert args.args[0] >= 0


async def test_latency_recorded_after_completion() -> None:
    """v1_latency is recorded once after the stream completes."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    handler._metrics.v1_latency.record.assert_called_once()


# ─── Fire-and-forget (no reply) ───────────────────────────────────────────────


async def test_fire_and_forget_no_respond_called() -> None:
    """When msg.reply is None, msg.respond() is NOT called."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    msg.respond.assert_not_called()


async def test_fire_and_forget_result_published() -> None:
    """Fire-and-forget: result is published to arc result subject."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hello"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    calls = handler._nc.publish.call_args_list
    result_calls = [c for c in calls if c.args[0] == "arc.reasoner.result"]
    assert len(result_calls) == 1


# ─── Request-reply ────────────────────────────────────────────────────────────


async def test_request_reply_respond_called() -> None:
    """When msg.reply is set, msg.respond() is called with the completion bytes."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hi"}], reply="INBOX.123")

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()
    raw = msg.respond.call_args.args[0]
    payload = json.loads(raw)
    assert payload["done"] is True


async def test_request_reply_also_publishes_to_result_subject() -> None:
    """Request-reply: result is ALSO published to arc result subject (dual publish)."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "hi"}], reply="INBOX.123")

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()
    calls = handler._nc.publish.call_args_list
    result_calls = [c for c in calls if c.args[0] == "arc.reasoner.result"]
    assert len(result_calls) == 1


# ─── Missing user message ─────────────────────────────────────────────────────


async def test_missing_user_message_publishes_error_no_crash() -> None:
    """No user-role message → error published to arc.reasoner.error, no raise."""
    handler = _make_handler()
    msg = _make_msg([{"role": "system", "content": "you are helpful"}], reply=None)

    await handler._handle(msg)

    handler._metrics.v1_errors_total.add.assert_called_once()
    calls = handler._nc.publish.call_args_list
    error_calls = [c for c in calls if c.args[0] == "arc.reasoner.error"]
    assert len(error_calls) == 1

    payload = json.loads(error_calls[0].args[1])
    assert "error" in payload


async def test_missing_user_message_with_reply_no_crash() -> None:
    """No user message + reply set → error published, msg.respond called with error."""
    handler = _make_handler()
    msg = _make_msg([{"role": "system", "content": "sys"}], reply="INBOX.err")

    await handler._handle(msg)

    calls = handler._nc.publish.call_args_list
    error_calls = [c for c in calls if c.args[0] == "arc.reasoner.error"]
    assert len(error_calls) == 1

    payload = json.loads(error_calls[0].args[1])
    assert "error" in payload


# ─── stream_graph exception ───────────────────────────────────────────────────


async def test_stream_graph_exception_publishes_error() -> None:
    """When stream_graph raises, error is published and no exception propagates."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "crash me"}], reply=None)

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_error):
        await handler._handle(msg)

    calls = handler._nc.publish.call_args_list
    error_calls = [c for c in calls if c.args[0] == "arc.reasoner.error"]
    assert len(error_calls) == 1

    payload = json.loads(error_calls[0].args[1])
    assert "stream failed" in payload["error"]
    handler._metrics.v1_errors_total.add.assert_called_once()


async def test_stream_graph_exception_with_reply_responds() -> None:
    """stream_graph exception + reply set → error also sent to inbox."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "boom"}], reply="INBOX.crash")

    with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_error):
        await handler._handle(msg)

    msg.respond.assert_awaited_once()
    raw = msg.respond.call_args.args[0]
    payload = json.loads(raw)
    assert "stream failed" in payload["error"]


# ─── No message content in logs ───────────────────────────────────────────────


async def test_no_message_content_in_debug_log() -> None:
    """_log.debug calls must not include user message content."""
    handler = _make_handler()
    secret_text = "super-secret-user-content-XYZ"
    msg = _make_msg([{"role": "user", "content": secret_text}], reply=None)

    debug_calls: list = []
    error_calls: list = []

    with patch("reasoner.openai_nats_handler._log") as mock_log:
        mock_log.debug = MagicMock(side_effect=lambda *a, **kw: debug_calls.append((a, kw)))
        mock_log.error = MagicMock(side_effect=lambda *a, **kw: error_calls.append((a, kw)))

        with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_chunks):
            await handler._handle(msg)

    all_calls = debug_calls + error_calls
    for args, kwargs in all_calls:
        combined = str(args) + str(kwargs)
        assert secret_text not in combined, f"Message content found in log call: {combined!r}"


async def test_no_message_content_in_error_log_on_exception() -> None:
    """_log.error calls on exception must not expose the user message content."""
    handler = _make_handler()
    secret_text = "private-user-data-ABC"
    msg = _make_msg([{"role": "user", "content": secret_text}], reply=None)

    error_calls: list = []

    with patch("reasoner.openai_nats_handler._log") as mock_log:
        mock_log.debug = MagicMock()
        mock_log.error = MagicMock(side_effect=lambda *a, **kw: error_calls.append((a, kw)))

        with patch("reasoner.openai_nats_handler.stream_graph", new=_mock_stream_error):
            await handler._handle(msg)

    for args, kwargs in error_calls:
        combined = str(args) + str(kwargs)
        assert secret_text not in combined, f"Message content found in error log: {combined!r}"


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
    assert handler.is_connected() is False


# ─── user_id derivation ───────────────────────────────────────────────────────


async def test_user_id_uses_req_user_when_set() -> None:
    """stream_graph receives the user_id from req.user when explicitly provided."""
    handler = _make_handler()
    payload = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "user": "explicit-user-123",
    }
    msg = MagicMock()
    msg.data = json.dumps(payload).encode()
    msg.subject = "reasoner.v1.chat"
    msg.reply = None
    msg.respond = AsyncMock()

    captured_user_id: list[str] = []

    async def fake_stream(graph, memory, user_id: str, text: str):
        captured_user_id.append(user_id)
        yield "ok"

    with patch("reasoner.openai_nats_handler.stream_graph", new=fake_stream):
        await handler._handle(msg)

    assert captured_user_id == ["explicit-user-123"]


async def test_user_id_derives_uuid_v5_when_absent() -> None:
    """When req.user is absent, user_id is a deterministic UUID v5 from message content."""
    handler = _make_handler()
    msg = _make_msg([{"role": "user", "content": "stable content"}], reply=None)

    captured_user_id: list[str] = []

    async def fake_stream(graph, memory, user_id: str, text: str):
        captured_user_id.append(user_id)
        yield "ok"

    with patch("reasoner.openai_nats_handler.stream_graph", new=fake_stream):
        await handler._handle(msg)

    assert len(captured_user_id) == 1
    derived = captured_user_id[0]
    parsed = uuid.UUID(derived)
    assert parsed.version == 5

    expected = _derive_user_id(
        [type("M", (), {"role": "user", "content": "stable content"})()]  # type: ignore[arg-type]
    )
    assert derived == expected


# ─── _derive_user_id unit test ────────────────────────────────────────────────


def test_derive_user_id_stable_across_calls() -> None:
    """_derive_user_id returns the same UUID v5 for identical message content."""
    from reasoner.models_v1 import ChatMessage

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
    from reasoner.models_v1 import ChatMessage

    messages_with_system = [
        ChatMessage(role="system", content="system prompt"),
        ChatMessage(role="user", content="test"),
    ]
    messages_without_system = [
        ChatMessage(role="user", content="test"),
    ]
    assert _derive_user_id(messages_with_system) == _derive_user_id(messages_without_system)
