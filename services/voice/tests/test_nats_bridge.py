"""Tests for the NATS bridge LLMBridgePort implementation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import nats.errors
import pytest

import voice.nats_bridge as bridge_module
from voice.interfaces import BridgeError, LLMBridgePort
from voice.nats_bridge import NATSBridge

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_msg(payload: dict[str, object]) -> MagicMock:
    """Return a mock NATS Msg with encoded JSON data."""
    msg = MagicMock()
    msg.data = json.dumps(payload).encode()
    return msg


# ─── Protocol conformance ─────────────────────────────────────────────────────


def test_nats_bridge_implements_llm_bridge_port() -> None:
    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    assert isinstance(b, LLMBridgePort)


# ─── connect() / disconnect() ─────────────────────────────────────────────────


async def test_connect_stores_client() -> None:
    mock_nc = AsyncMock()
    with patch("voice.nats_bridge.nats.connect", return_value=mock_nc) as mock_connect:
        await bridge_module.connect("nats://localhost:4222")
        mock_connect.assert_awaited_once_with("nats://localhost:4222")
        assert bridge_module._nc is mock_nc


async def test_disconnect_drains_and_clears() -> None:
    mock_nc = AsyncMock()
    bridge_module._nc = mock_nc

    await bridge_module.disconnect()

    mock_nc.drain.assert_awaited_once()
    mock_nc.close.assert_awaited_once()
    assert bridge_module._nc is None


async def test_disconnect_when_already_none_is_safe() -> None:
    bridge_module._nc = None
    await bridge_module.disconnect()  # must not raise


# ─── reason() — happy path ────────────────────────────────────────────────────


async def test_reason_returns_response_field() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"request_id": "corr-1", "response": "Hello from Sherlock"})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    result = await b.reason(
        transcript="What is 2+2?",
        session_id="sess-abc",
        correlation_id="corr-1",
    )

    assert result == "Hello from Sherlock"


async def test_reason_falls_back_to_text_field() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"request_id": "corr-2", "text": "Fallback text"})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    result = await b.reason(
        transcript="Hello",
        session_id="sess-abc",
        correlation_id="corr-2",
    )

    assert result == "Fallback text"


async def test_reason_returns_empty_string_when_no_text_field() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"request_id": "corr-3", "done": True, "ttft_ms": 42})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    result = await b.reason(
        transcript="Hello",
        session_id="sess-abc",
        correlation_id="corr-3",
    )

    assert result == ""


async def test_reason_sends_correct_payload() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"response": "ok"})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=3000)
    await b.reason(
        transcript="Test query",
        session_id="session-42",
        correlation_id="corr-xyz",
    )

    mock_nc.request.assert_awaited_once()
    call_args = mock_nc.request.call_args
    subject = call_args.args[0]
    raw_payload = call_args.args[1]
    timeout = call_args.kwargs.get("timeout") or call_args.args[2]

    assert subject == "arc.reasoner.request"
    decoded = json.loads(raw_payload.decode())
    assert decoded["request_id"] == "corr-xyz"
    assert decoded["user_id"] == "session-42"
    assert decoded["text"] == "Test query"
    assert timeout == pytest.approx(3.0)


# ─── reason() — error cases ───────────────────────────────────────────────────


async def test_reason_raises_bridge_error_on_timeout() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(side_effect=nats.errors.TimeoutError())
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=500)
    with pytest.raises(BridgeError) as exc_info:
        await b.reason(
            transcript="Will time out",
            session_id="sess-timeout",
            correlation_id="corr-timeout",
        )

    err = exc_info.value
    assert err.is_timeout is True
    assert err.error_type == "bridge_timeout"


async def test_reason_raises_bridge_error_on_reasoner_error_field() -> None:
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"request_id": "corr-err", "error": "LLM unavailable"})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    with pytest.raises(BridgeError) as exc_info:
        await b.reason(
            transcript="Hello",
            session_id="sess-err",
            correlation_id="corr-err",
        )

    err = exc_info.value
    assert err.is_timeout is False
    assert err.error_type == "bridge_error"
    assert "LLM unavailable" in str(err)


async def test_reason_raises_bridge_error_when_not_connected() -> None:
    bridge_module._nc = None

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    with pytest.raises(BridgeError) as exc_info:
        await b.reason(
            transcript="Hello",
            session_id="sess-disconnected",
            correlation_id="corr-disconnected",
        )

    err = exc_info.value
    assert err.is_timeout is False
    assert err.error_type == "bridge_error"


async def test_reason_raises_bridge_error_on_invalid_json() -> None:
    mock_nc = AsyncMock()
    bad_msg = MagicMock()
    bad_msg.data = b"not-valid-json!!!"
    mock_nc.request = AsyncMock(return_value=bad_msg)
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=5000)
    with pytest.raises(BridgeError) as exc_info:
        await b.reason(
            transcript="Hello",
            session_id="sess-bad-json",
            correlation_id="corr-bad-json",
        )

    err = exc_info.value
    assert err.is_timeout is False
    assert err.error_type == "bridge_error"


# ─── Timeout conversion ───────────────────────────────────────────────────────


async def test_timeout_ms_converted_to_seconds() -> None:
    """Verify timeout_ms is divided by 1000 before passing to nc.request()."""
    mock_nc = AsyncMock()
    mock_nc.request = AsyncMock(
        return_value=_make_msg({"response": "ok"})
    )
    bridge_module._nc = mock_nc

    b = NATSBridge(subject="arc.reasoner.request", timeout_ms=10000)
    await b.reason(transcript="Hi", session_id="s", correlation_id="c")

    call_args = mock_nc.request.call_args
    # timeout may be positional or keyword
    timeout = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs["timeout"]

    assert timeout == pytest.approx(10.0)
