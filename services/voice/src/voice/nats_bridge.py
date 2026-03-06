"""NATS bridge — LLMBridgePort implementation for arc-reasoner request-reply.

Sends a reasoning request to arc-reasoner over NATS and waits for the reply.
Uses nats-py's nc.request() which handles the inbox/reply subject automatically.

Request payload (matches arc-reasoner nats_handler.py expectations):
    {"request_id": <correlation_id>, "user_id": <session_id>, "text": <transcript>}

Success reply (from reasoner completion signal):
    {"request_id": ..., "done": true, "response": <text>, ...}

Error reply:
    {"request_id": ..., "error": <message>, ...}
"""

from __future__ import annotations

import json
import time

import nats
import nats.errors
import structlog
from nats.aio.client import Client as NATSClient

from voice.interfaces import BridgeError
from voice.observability import get_bridge_histogram, get_tracer

_log = structlog.get_logger(__name__)

# ─── Module-level singleton ────────────────────────────────────────────────────

_nc: NATSClient | None = None


async def connect(nats_url: str) -> None:
    """Connect to NATS and store the connection as a module-level singleton."""
    global _nc
    _nc = await nats.connect(nats_url)
    _log.info("nats_bridge connected", url=nats_url)


async def disconnect() -> None:
    """Drain and close the NATS connection."""
    global _nc
    if _nc is not None:
        await _nc.drain()
        await _nc.close()
        _nc = None
        _log.info("nats_bridge disconnected")


# ─── LLMBridgePort implementation ─────────────────────────────────────────────


class NATSBridge:
    """LLMBridgePort that routes voice turns to arc-reasoner over NATS request-reply.

    Uses the module-level ``_nc`` singleton set by ``connect()`` / cleared by
    ``disconnect()``.  The connection lifecycle is managed by main.py's lifespan
    handler — this class only handles the per-request logic.
    """

    def __init__(self, subject: str, timeout_ms: int) -> None:
        self._subject = subject
        self._timeout_ms = timeout_ms

    async def reason(
        self,
        transcript: str,
        session_id: str,
        correlation_id: str,
    ) -> str:
        """Send a voice turn to arc-reasoner and return the response text.

        Maps voice fields to the reasoner's NATS contract:
            session_id  → user_id
            transcript  → text
            correlation_id → request_id

        Raises:
            BridgeError(is_timeout=True)  — NATS request timed out.
            BridgeError(is_timeout=False) — Reasoner returned an error payload.
        """
        if _nc is None:
            raise BridgeError(
                "NATS connection is not established — call connect() first",
                is_timeout=False,
                error_type="bridge_error",
            )

        tracer = get_tracer()
        histogram = get_bridge_histogram()

        payload = json.dumps(
            {
                "request_id": correlation_id,
                "user_id": session_id,
                "text": transcript,
            }
        ).encode()

        timeout_secs = self._timeout_ms / 1000.0
        start = time.monotonic()

        with tracer.start_as_current_span("voice.bridge.reason") as span:
            span.set_attribute("voice.session_id", session_id)
            span.set_attribute("voice.correlation_id", correlation_id)
            span.set_attribute("nats.subject", self._subject)

            try:
                msg = await _nc.request(self._subject, payload, timeout=timeout_secs)
            except nats.errors.TimeoutError as exc:
                elapsed = time.monotonic() - start
                histogram.record(elapsed, {"outcome": "timeout"})
                span.set_attribute("voice.bridge.outcome", "timeout")
                _log.warning(
                    "nats_bridge timeout",
                    subject=self._subject,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    elapsed_s=elapsed,
                )
                raise BridgeError(
                    f"arc-reasoner did not reply within {self._timeout_ms} ms",
                    is_timeout=True,
                    error_type="bridge_timeout",
                ) from exc

            elapsed = time.monotonic() - start
            histogram.record(elapsed, {"outcome": "success"})

            try:
                data: dict[str, object] = json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                span.set_attribute("voice.bridge.outcome", "parse_error")
                raise BridgeError(
                    f"Failed to parse reasoner reply: {exc}",
                    is_timeout=False,
                    error_type="bridge_error",
                ) from exc

            if "error" in data:
                span.set_attribute("voice.bridge.outcome", "reasoner_error")
                histogram.record(elapsed, {"outcome": "bridge_error"})
                _log.warning(
                    "nats_bridge reasoner error",
                    subject=self._subject,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    error=data["error"],
                )
                raise BridgeError(
                    f"arc-reasoner returned error: {data['error']}",
                    is_timeout=False,
                    error_type="bridge_error",
                )

            # Extract response text — prefer "response" field, fall back to "text"
            response_text = data.get("response") or data.get("text") or ""
            span.set_attribute("voice.bridge.outcome", "success")
            span.set_attribute("voice.bridge.elapsed_s", elapsed)

            _log.debug(
                "nats_bridge reply received",
                subject=self._subject,
                session_id=session_id,
                correlation_id=correlation_id,
                elapsed_s=elapsed,
            )

            return str(response_text)
