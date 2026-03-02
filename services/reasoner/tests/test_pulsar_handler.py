"""Unit tests for sherlock.pulsar_handler.PulsarHandler.

Tests cover the _process() dispatch logic, both ack paths (Path A: error string
returned, Path B: exception raised), negative-ack on missing request_id,
asyncio.to_thread usage, and AsyncAPI schema conformance.

asyncio_mode = "auto" from pyproject.toml — no explicit @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jsonschema
import pytest
import yaml

from sherlock.config import Settings
from sherlock.graph import GraphErrorResponse
from sherlock.observability import SherlockMetrics
from sherlock.pulsar_handler import PulsarHandler


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.pulsar_url = "pulsar://localhost:6650"
    s.pulsar_request_topic = "persistent://public/default/sherlock-requests"
    s.pulsar_result_topic = "persistent://public/default/sherlock-results"
    s.pulsar_subscription = "sherlock-workers"
    return s


def _make_metrics() -> MagicMock:
    m = MagicMock(spec=SherlockMetrics)
    m.requests_total = MagicMock()
    m.requests_total.add = MagicMock()
    m.errors_total = MagicMock()
    m.errors_total.add = MagicMock()
    m.latency = MagicMock()
    m.latency.record = MagicMock()
    return m


def _make_handler() -> PulsarHandler:
    """Return a PulsarHandler with all dependencies mocked (no live Pulsar connection)."""
    return PulsarHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=_make_settings(),
        metrics=_make_metrics(),
    )


def _make_pulsar_msg(data: bytes) -> MagicMock:
    msg = MagicMock()
    msg.data = MagicMock(return_value=data)
    return msg


async def _fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Coroutine that calls the blocking function synchronously (test helper)."""
    return fn(*args, **kwargs)


# ─── _process() — happy path (Path A: normal response) ────────────────────────


async def test_process_and_ack() -> None:
    """Successful invoke_graph: producer.send called with result, consumer.acknowledge called."""
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    msg = _make_pulsar_msg(b'{"request_id": "abc", "user_id": "u1", "text": "hi"}')

    with (
        patch(
            "sherlock.pulsar_handler.invoke_graph",
            new_callable=AsyncMock,
            return_value="response",
        ),
        patch("asyncio.to_thread", side_effect=_fake_to_thread),
    ):
        await handler._process(msg)

    # producer.send must have been called (via to_thread)
    mock_producer.send.assert_called_once()
    raw = mock_producer.send.call_args.args[0]
    body = json.loads(raw.decode())
    assert body["request_id"] == "abc"
    assert body["text"] == "response"
    assert isinstance(body["latency_ms"], int)

    mock_consumer.acknowledge.assert_called_once_with(msg)
    mock_consumer.negative_acknowledge.assert_not_called()


# ─── _process() — Path A: error string from error_handler (GAP-6) ─────────────


async def test_error_handler_result_published_and_acked() -> None:
    """Path A: invoke_graph raises GraphErrorResponse (error_handler exhausted retries).

    The handler must:
    - Publish {"request_id":..., "error": str, "latency_ms": N} to sherlock-results
    - Call consumer.acknowledge (do NOT redeliver — message was fully processed)
    - NOT call consumer.negative_acknowledge
    """
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    error_msg = "I'm unable to process your request at the moment (retried 3 times)."
    msg = _make_pulsar_msg(b'{"request_id": "xyz", "user_id": "u2", "text": "analyze"}')

    with (
        patch(
            "sherlock.pulsar_handler.invoke_graph",
            new_callable=AsyncMock,
            side_effect=GraphErrorResponse(error_msg),
        ),
        patch("asyncio.to_thread", side_effect=_fake_to_thread),
    ):
        await handler._process(msg)

    # Error result published with "error" key (not "text") — asyncapi contract
    mock_producer.send.assert_called_once()
    raw = mock_producer.send.call_args.args[0]
    body = json.loads(raw.decode())
    assert body["request_id"] == "xyz"
    assert body["error"] == error_msg
    assert "text" not in body
    assert isinstance(body["latency_ms"], int)

    # Message is acknowledged (Path A — do NOT redeliver)
    mock_consumer.acknowledge.assert_called_once_with(msg)
    mock_consumer.negative_acknowledge.assert_not_called()


# ─── _process() — Path B: unhandled exception → nack ─────────────────────────


async def test_unhandled_exception_triggers_negative_ack() -> None:
    """When invoke_graph raises (Path B), nack is issued and no exception propagates."""
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    msg = _make_pulsar_msg(b'{"request_id": "abc", "user_id": "u1", "text": "crash"}')

    with (
        patch(
            "sherlock.pulsar_handler.invoke_graph",
            new_callable=AsyncMock,
            side_effect=RuntimeError("gpu oom"),
        ),
        patch("asyncio.to_thread", side_effect=_fake_to_thread),
    ):
        # Must not propagate
        await handler._process(msg)

    mock_consumer.negative_acknowledge.assert_called_once_with(msg)
    mock_consumer.acknowledge.assert_not_called()
    mock_producer.send.assert_not_called()


# ─── _process() — missing request_id → nack ───────────────────────────────────


async def test_missing_request_id_triggers_nack() -> None:
    """Payload without request_id causes a KeyError which triggers negative_acknowledge."""
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    msg = _make_pulsar_msg(b'{"user_id": "u1", "text": "hi"}')

    with patch("asyncio.to_thread", side_effect=_fake_to_thread):
        await handler._process(msg)

    mock_consumer.negative_acknowledge.assert_called_once_with(msg)
    mock_consumer.acknowledge.assert_not_called()


# ─── asyncio.to_thread usage (GAP-2 test) ─────────────────────────────────────


async def test_asyncio_to_thread_used_for_blocking_calls() -> None:
    """Verify asyncio.to_thread is invoked for producer.send and consumer.acknowledge."""
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    msg = _make_pulsar_msg(b'{"request_id": "t1", "user_id": "u1", "text": "test"}')

    to_thread_calls: list[Any] = []

    async def _recording_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        to_thread_calls.append((fn, args, kwargs))
        return fn(*args, **kwargs)

    with (
        patch(
            "sherlock.pulsar_handler.invoke_graph",
            new_callable=AsyncMock,
            return_value="ok",
        ),
        patch("asyncio.to_thread", side_effect=_recording_to_thread),
    ):
        await handler._process(msg)

    # At least two to_thread calls: producer.send and consumer.acknowledge
    fns_called = [call[0] for call in to_thread_calls]
    assert mock_producer.send in fns_called
    assert mock_consumer.acknowledge in fns_called


async def test_asyncio_to_thread_used_for_negative_ack() -> None:
    """Verify asyncio.to_thread is invoked for consumer.negative_acknowledge on error path."""
    handler = _make_handler()

    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()
    mock_consumer.negative_acknowledge = MagicMock()

    mock_producer = MagicMock()
    mock_producer.send = MagicMock()

    handler._consumer = mock_consumer
    handler._producer = mock_producer

    msg = _make_pulsar_msg(b'{"request_id": "t2", "user_id": "u1", "text": "crash"}')

    to_thread_calls: list[Any] = []

    async def _recording_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
        to_thread_calls.append((fn, args, kwargs))
        return fn(*args, **kwargs)

    with (
        patch(
            "sherlock.pulsar_handler.invoke_graph",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch("asyncio.to_thread", side_effect=_recording_to_thread),
    ):
        await handler._process(msg)

    fns_called = [call[0] for call in to_thread_calls]
    assert mock_consumer.negative_acknowledge in fns_called


# ─── AsyncAPI schema conformance (GAP-2) ──────────────────────────────────────


def _load_asyncapi_schema(schema_name: str) -> dict[str, Any]:
    contracts_path = (
        pathlib.Path(__file__).parent.parent / "contracts" / "asyncapi.yaml"
    )
    with contracts_path.open() as fh:
        spec: dict[str, Any] = yaml.safe_load(fh)
    return spec["components"]["schemas"][schema_name]  # type: ignore[return-value]


def test_pulsar_result_payload_matches_asyncapi_schema() -> None:
    """ReasoningResultPayload schema from asyncapi.yaml accepts a valid result payload."""
    schema = _load_asyncapi_schema("ReasoningResultPayload")
    payload = {
        "request_id": "abc",
        "user_id": "u1",
        "text": "response",
        "latency_ms": 100,
    }
    # Should not raise
    jsonschema.validate(instance=payload, schema=schema)


def test_pulsar_result_payload_rejects_missing_required_fields() -> None:
    """ReasoningResultPayload schema rejects payloads missing required fields."""
    schema = _load_asyncapi_schema("ReasoningResultPayload")
    # Missing latency_ms (required)
    invalid_payload = {"request_id": "abc", "user_id": "u1", "text": "response"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_payload, schema=schema)


def test_pulsar_durable_request_payload_matches_asyncapi_schema() -> None:
    """DurableReasoningRequestPayload schema accepts a valid inbound Pulsar payload."""
    schema = _load_asyncapi_schema("DurableReasoningRequestPayload")
    payload = {"request_id": "req-abc-123", "user_id": "u1", "text": "analyze this"}
    jsonschema.validate(instance=payload, schema=schema)
