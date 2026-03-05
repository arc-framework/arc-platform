"""Unit tests for reasoner.nats_handler.NATSHandler (Phase 1 streaming path).

Tests cover:
  - stream_graph() token chunk publishing to arc.reasoner.stream.{request_id}
  - Completion signal publishing to arc.reasoner.result
  - Error publishing to arc.reasoner.error
  - Fire-and-forget vs request-reply semantics
  - TTFT histogram recording
  - AsyncAPI schema conformance

asyncio_mode = "auto" from pyproject.toml — no explicit @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jsonschema
import pytest
import yaml

from reasoner.config import Settings
from reasoner.nats_handler import NATSHandler
from reasoner.observability import SherlockMetrics


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.nats_url = "nats://localhost:4222"
    s.nats_subject = "reasoner.request"
    s.arc_nats_request_subject = "arc.reasoner.request"
    s.arc_nats_stream_prefix = "arc.reasoner.stream"
    s.arc_nats_result_subject = "arc.reasoner.result"
    s.arc_nats_error_subject = "arc.reasoner.error"
    s.nats_queue_group = "reasoner_workers"
    s.nats_enabled = True
    return s


def _make_metrics() -> MagicMock:
    m = MagicMock(spec=SherlockMetrics)
    m.requests_total = MagicMock()
    m.requests_total.add = MagicMock()
    m.errors_total = MagicMock()
    m.errors_total.add = MagicMock()
    m.latency = MagicMock()
    m.latency.record = MagicMock()
    m.ttft_seconds = MagicMock()
    m.ttft_seconds.record = MagicMock()
    return m


def _make_handler() -> NATSHandler:
    """Return a NATSHandler with all dependencies mocked (no live NATS connection)."""
    handler = NATSHandler(
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


def _make_msg(data: bytes, reply: str | None) -> MagicMock:
    msg = MagicMock()
    msg.data = data
    msg.subject = "arc.reasoner.request"
    msg.reply = reply
    msg.respond = AsyncMock()
    return msg


async def _mock_stream_chunks(*args: Any, **kwargs: Any):
    """Async generator yielding two token chunks."""
    yield "Hello"
    yield " world"


async def _mock_stream_empty(*args: Any, **kwargs: Any):
    """Async generator yielding no tokens."""
    return
    yield  # make it an async generator


async def _mock_stream_error(*args: Any, **kwargs: Any):
    """Async generator that raises immediately."""
    raise RuntimeError("stream failed")
    yield  # make it an async generator


# ─── Token chunk publishing ────────────────────────────────────────────────────


async def test_token_chunks_published_to_stream_subject() -> None:
    """Token chunks are published to arc.reasoner.stream.{request_id}."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    publish_calls = handler._nc.publish.call_args_list
    stream_calls = [
        call for call in publish_calls
        if call.args[0].startswith("arc.reasoner.stream.")
    ]
    assert len(stream_calls) == 2

    first_chunk = json.loads(stream_calls[0].args[1].decode())
    assert "request_id" in first_chunk
    assert first_chunk["chunk"] in ("Hello", " world")


async def test_completion_signal_published_to_result_subject() -> None:
    """After all chunks, a completion signal is published to arc.reasoner.result."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    result_calls = [
        call for call in handler._nc.publish.call_args_list
        if call.args[0] == "arc.reasoner.result"
    ]
    assert len(result_calls) == 1

    completion = json.loads(result_calls[0].args[1].decode())
    assert completion["done"] is True
    assert "request_id" in completion
    assert "user_id" in completion
    assert isinstance(completion["ttft_ms"], int)
    assert isinstance(completion["latency_ms"], int)


async def test_ttft_recorded_on_first_token() -> None:
    """ttft_seconds histogram is recorded exactly once, on the first token."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    handler._metrics.ttft_seconds.record.assert_called_once()
    recorded_value = handler._metrics.ttft_seconds.record.call_args.args[0]
    assert recorded_value >= 0


# ─── Fire-and-forget ──────────────────────────────────────────────────────────


async def test_fire_and_forget_no_respond() -> None:
    """When msg.reply is None, msg.respond() is NOT called."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    msg.respond.assert_not_called()


# ─── Request-reply ────────────────────────────────────────────────────────────


async def test_request_reply_responds_with_completion() -> None:
    """When msg.reply is set, msg.respond() is called with completion JSON."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply="INBOX.123")

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_chunks):
        await handler._handle(msg)

    msg.respond.assert_called_once()
    body = json.loads(msg.respond.call_args.args[0].decode())
    assert body["done"] is True
    assert "request_id" in body
    assert isinstance(body["latency_ms"], int)


# ─── Error path ───────────────────────────────────────────────────────────────


async def test_error_published_to_error_subject() -> None:
    """When stream_graph raises, error is published to arc.reasoner.error."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_error):
        await handler._handle(msg)

    error_calls = [
        call for call in handler._nc.publish.call_args_list
        if call.args[0] == "arc.reasoner.error"
    ]
    assert len(error_calls) == 1
    error_payload = json.loads(error_calls[0].args[1].decode())
    assert error_payload["error"] == "stream failed"


async def test_error_responds_when_reply_set() -> None:
    """On error with reply set, msg.respond() sends the error JSON."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply="INBOX.xxx")

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_error):
        await handler._handle(msg)

    msg.respond.assert_called_once()
    body = json.loads(msg.respond.call_args.args[0].decode())
    assert body["error"] == "stream failed"
    assert isinstance(body["latency_ms"], int)


async def test_error_increments_error_counter() -> None:
    """Errors increment the errors_total metric."""
    handler = _make_handler()
    msg = _make_msg(b'{"user_id": "u1", "text": "hi"}', reply=None)

    with patch("reasoner.nats_handler.stream_graph", new=_mock_stream_error):
        await handler._handle(msg)

    handler._metrics.errors_total.add.assert_called_once_with(1, {"transport": "nats"})


# ─── is_connected() ───────────────────────────────────────────────────────────


def test_is_connected_true_after_connect() -> None:
    """is_connected() reflects the underlying NATS client connection state."""
    handler = _make_handler()
    mock_nc = MagicMock()
    mock_nc.is_connected = True
    handler._nc = mock_nc

    assert handler.is_connected() is True


def test_is_connected_false_when_nc_is_none() -> None:
    """is_connected() returns False when _nc has not been set."""
    handler = NATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=_make_settings(),
        metrics=_make_metrics(),
    )
    assert handler.is_connected() is False


# ─── AsyncAPI schema conformance ──────────────────────────────────────────────


def test_nats_request_payload_matches_asyncapi_schema() -> None:
    """ReasoningRequestPayload schema from asyncapi.yaml accepts a valid payload."""
    contracts_path = (
        pathlib.Path(__file__).parent.parent / "contracts" / "asyncapi.yaml"
    )

    with contracts_path.open() as fh:
        spec: dict[str, Any] = yaml.safe_load(fh)

    schema = spec["components"]["schemas"]["ReasoningRequestPayload"]
    payload = {"user_id": "u1", "text": "hello"}

    # Should not raise
    jsonschema.validate(instance=payload, schema=schema)


def test_nats_request_payload_rejects_empty_user_id() -> None:
    """ReasoningRequestPayload schema rejects a payload with minLength violation."""
    contracts_path = (
        pathlib.Path(__file__).parent.parent / "contracts" / "asyncapi.yaml"
    )

    with contracts_path.open() as fh:
        spec: dict[str, Any] = yaml.safe_load(fh)

    schema = spec["components"]["schemas"]["ReasoningRequestPayload"]
    invalid_payload = {"user_id": "", "text": "hello"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_payload, schema=schema)


def test_arc_stream_chunk_schema_validates() -> None:
    """ArcStreamChunkPayload schema accepts a valid chunk payload."""
    contracts_path = (
        pathlib.Path(__file__).parent.parent / "contracts" / "asyncapi.yaml"
    )

    with contracts_path.open() as fh:
        spec: dict[str, Any] = yaml.safe_load(fh)

    schema = spec["components"]["schemas"]["ArcStreamChunkPayload"]
    payload = {"request_id": "550e8400-e29b-41d4-a716-446655440000", "chunk": " databases"}

    jsonschema.validate(instance=payload, schema=schema)
