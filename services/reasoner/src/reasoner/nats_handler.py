import asyncio
import json
import re
import time
import uuid
from typing import Any

import nats
import structlog
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from reasoner.config import Settings
from reasoner.graph import stream_graph
from reasoner.observability import SherlockMetrics

_log = structlog.get_logger(__name__)

# ─── Guard patterns ───────────────────────────────────────────────────────────

_INJECTION_PATTERNS = re.compile(
    r"ignore (previous|all|prior) (instructions?|prompts?|system)",
    re.IGNORECASE,
)
_UNSAFE_OUTPUT_PATTERNS = re.compile(
    r"\b(CONFIDENTIAL|SECRET|PASSWORD|API_KEY)\b",
    re.IGNORECASE,
)


class NATSHandler:
    """NATS streaming subscriber for real-time reasoning requests.

    Subscribes to both arc.reasoner.request (new arc.* path) and the legacy
    reasoner.request subject for backward compatibility.

    Each request spawns a stream_graph() async generator that publishes token
    chunks to arc.reasoner.stream.{request_id} as they arrive from the LLM,
    giving clients sub-200ms TTFT. A completion signal is published to
    arc.reasoner.result when the stream ends.

    Legacy request-reply callers (msg.reply set) receive the completion payload
    directly in addition to the stream subject.
    """

    def __init__(
        self,
        graph: Any,
        memory: Any,
        settings: Settings,
        metrics: SherlockMetrics,
    ) -> None:
        self._graph = graph
        self._memory = memory
        self._settings = settings
        self._metrics = metrics
        self._nc: NATSClient | None = None

    async def connect(self) -> None:
        """Establish NATS connection."""
        self._nc = await nats.connect(self._settings.nats_url)

    async def subscribe(self) -> None:
        """Subscribe to arc.* and legacy request subjects with queue group load balancing."""
        if self._nc is None:
            raise RuntimeError("NATSHandler.connect() must be called before subscribe()")
        # New arc.* streaming subject
        await self._nc.subscribe(
            self._settings.arc_nats_request_subject,
            queue=self._settings.nats_queue_group,
            cb=self._handle,
        )
        # Legacy subject — kept for backward compatibility
        await self._nc.subscribe(
            self._settings.nats_subject,
            queue=self._settings.nats_queue_group,
            cb=self._handle,
        )

    async def _handle(self, msg: Msg) -> None:
        """Process an incoming NATS message using stream_graph() for token streaming.

        Guard (T032): when SHERLOCK_GUARD_ENABLED, runs pre-check before stream_graph
        and post-check on the accumulated response before sending the completion signal.

        Fallback (T034): wraps stream_graph in asyncio.wait_for with TTFT timeout.
        On TimeoutError, retries up to nats_max_retries times with exponential backoff
        (100ms → 1s → 10s). After all retries exhausted, queues to durable subject and
        then to DLQ.

        Publishes token chunks to arc.reasoner.stream.{request_id} as they arrive.
        Sends a completion signal to arc.reasoner.result when the stream ends.
        Records ttft_seconds from request receive to first token emitted.
        """
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        self._metrics.requests_total.add(1, {"transport": "nats"})
        _log.debug(
            "nats recv",
            event_type="message_received",
            subject=msg.subject,
            transport="nats",
            request_id=request_id,
        )

        try:
            payload = json.loads(msg.data.decode())
            user_id: str = payload["user_id"]
            text: str = payload["text"]

            # T032: Guard pre-check (fail-open when disabled)
            if self._settings.guard_enabled and _INJECTION_PATTERNS.search(text):
                guard_payload = json.dumps({
                    "request_id": request_id,
                    "reason": "injection_detected",
                })
                if self._nc is not None:
                    await self._nc.publish(
                        self._settings.arc_nats_guard_rejected_subject,
                        guard_payload.encode(),
                    )
                if msg.reply:
                    await msg.respond(guard_payload.encode())
                return

            stream_subject = f"{self._settings.arc_nats_stream_prefix}.{request_id}"
            backoffs = [0.0, 0.1, 1.0, 10.0]
            attempt = 0

            while attempt <= self._settings.nats_max_retries:
                if attempt > 0 and attempt < len(backoffs):
                    await asyncio.sleep(backoffs[attempt])

                try:
                    ttft_ms = 0
                    accumulated: list[str] = []

                    gen = stream_graph(self._graph, self._memory, user_id, text)
                    # TTFT timeout gate: first token must arrive within nats_ttft_timeout
                    first_chunk: str = await asyncio.wait_for(
                        gen.__anext__(), timeout=self._settings.nats_ttft_timeout
                    )
                    ttft_ms = int((time.monotonic() - start) * 1000)
                    self._metrics.ttft_seconds.record(ttft_ms / 1000, {"transport": "nats"})
                    accumulated.append(first_chunk)

                    chunk_payload = json.dumps({"request_id": request_id, "chunk": first_chunk})
                    if self._nc is not None:
                        await self._nc.publish(stream_subject, chunk_payload.encode())

                    # Stream remaining chunks
                    async for chunk in gen:
                        accumulated.append(chunk)
                        chunk_payload = json.dumps({"request_id": request_id, "chunk": chunk})
                        if self._nc is not None:
                            await self._nc.publish(stream_subject, chunk_payload.encode())

                    latency_ms = int((time.monotonic() - start) * 1000)
                    self._metrics.latency.record(latency_ms, {"transport": "nats"})
                    response_text = "".join(accumulated)

                    # T032: Guard post-check — before sending completion signal
                    unsafe = (
                        self._settings.guard_enabled
                        and _UNSAFE_OUTPUT_PATTERNS.search(response_text)
                    )
                    if unsafe:
                        guard_payload = json.dumps({
                            "request_id": request_id,
                            "reason": "unsafe_output_detected",
                        })
                        if self._nc is not None:
                            await self._nc.publish(
                                self._settings.arc_nats_guard_intercepted_subject,
                                guard_payload.encode(),
                            )
                        return

                    completion_payload = json.dumps({
                        "request_id": request_id,
                        "user_id": user_id,
                        "done": True,
                        "ttft_ms": ttft_ms,
                        "latency_ms": latency_ms,
                    })
                    if self._nc is not None:
                        await self._nc.publish(
                            self._settings.arc_nats_result_subject,
                            completion_payload.encode(),
                        )

                    if msg.reply:
                        await msg.respond(completion_payload.encode())
                    return  # success

                except (TimeoutError, StopAsyncIteration):
                    if attempt == 0 and self._nc is not None:
                        # First timeout: queue to durable subject for async processing
                        durable_payload = json.dumps({
                            "request_id": request_id,
                            "user_id": user_id,
                            "text": text,
                        })
                        await self._nc.publish(
                            self._settings.arc_nats_durable_subject,
                            durable_payload.encode(),
                        )
                    attempt += 1

            # All retries exhausted → DLQ
            if self._nc is not None:
                dlq_payload = json.dumps({
                    "request_id": request_id,
                    "user_id": user_id,
                    "text": text,
                    "reason": "max_retries_exhausted",
                })
                await self._nc.publish(
                    self._settings.arc_nats_dlq_subject,
                    dlq_payload.encode(),
                )

        except Exception as exc:
            self._metrics.errors_total.add(1, {"transport": "nats"})
            latency_ms = int((time.monotonic() - start) * 1000)
            _log.error(
                "nats error",
                event_type="exception",
                error=str(exc),
                transport="nats",
                request_id=request_id,
            )

            error_payload = json.dumps({
                "request_id": request_id,
                "error": str(exc),
                "latency_ms": latency_ms,
            })
            if self._nc is not None:
                await self._nc.publish(
                    self._settings.arc_nats_error_subject,
                    error_payload.encode(),
                )

            if msg.reply:
                await msg.respond(error_payload.encode())

    def is_connected(self) -> bool:
        """Return True if the NATS connection is active, or if NATS is disabled."""
        if not self._settings.nats_enabled:
            return True
        return self._nc is not None and self._nc.is_connected

    async def close(self) -> None:
        """Drain and close the NATS connection."""
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
            self._nc = None
