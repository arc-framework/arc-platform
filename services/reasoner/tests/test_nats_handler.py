"""Unit tests for sherlock.nats_handler.NATSHandler.

Tests cover the _handle() dispatch logic, fire-and-forget semantics, error
response on exception, connection state, and AsyncAPI schema conformance.

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

from sherlock.config import Settings
from sherlock.nats_handler import NATSHandler
from sherlock.observability import SherlockMetrics


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    s = MagicMock(spec=Settings)
    s.nats_url = "nats://localhost:4222"
    s.nats_subject = "sherlock.request"
    s.nats_queue_group = "sherlock_workers"
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


def _make_handler() -> NATSHandler:
    """Return a NATSHandler with all dependencies mocked (no live NATS connection)."""
    return NATSHandler(
        graph=MagicMock(),
        memory=AsyncMock(),
        settings=_make_settings(),
        metrics=_make_metrics(),
    )


def _make_msg(data: bytes, reply: str | None) -> MagicMock:
    msg = MagicMock()
    msg.data = data
    msg.reply = reply
    msg.respond = AsyncMock()
    return msg


# ─── _handle() — request-reply ────────────────────────────────────────────────


async def test_request_reply() -> None:
    """When msg.reply is set, respond() is called with user_id, text, latency_ms."""
    handler = _make_handler()
    msg = _make_msg(
        data=b'{"user_id": "u1", "text": "hi"}',
        reply="INBOX.123",
    )

    with patch(
        "sherlock.nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="response text",
    ):
        await handler._handle(msg)

    msg.respond.assert_called_once()
    raw = msg.respond.call_args.args[0]
    body = json.loads(raw.decode())
    assert body["user_id"] == "u1"
    assert body["text"] == "response text"
    assert isinstance(body["latency_ms"], int)


# ─── _handle() — fire-and-forget ──────────────────────────────────────────────


async def test_fire_and_forget() -> None:
    """When msg.reply is None, respond() is NOT called and no exception is raised."""
    handler = _make_handler()
    msg = _make_msg(
        data=b'{"user_id": "u1", "text": "hi"}',
        reply=None,
    )

    with patch(
        "sherlock.nats_handler.invoke_graph",
        new_callable=AsyncMock,
        return_value="response text",
    ):
        await handler._handle(msg)

    msg.respond.assert_not_called()


# ─── _handle() — error path ───────────────────────────────────────────────────


async def test_error_response_on_exception() -> None:
    """When invoke_graph raises, respond() is called with error and latency_ms."""
    handler = _make_handler()
    msg = _make_msg(
        data=b'{"user_id": "u1", "text": "hi"}',
        reply="INBOX.xxx",
    )

    with patch(
        "sherlock.nats_handler.invoke_graph",
        new_callable=AsyncMock,
        side_effect=RuntimeError("oops"),
    ):
        await handler._handle(msg)

    msg.respond.assert_called_once()
    raw = msg.respond.call_args.args[0]
    body = json.loads(raw.decode())
    assert body["error"] == "oops"
    assert isinstance(body["latency_ms"], int)


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
    handler = _make_handler()
    assert handler.is_connected() is False


# ─── AsyncAPI schema conformance (GAP-2) ──────────────────────────────────────


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
