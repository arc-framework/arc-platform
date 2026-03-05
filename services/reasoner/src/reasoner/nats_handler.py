import json
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

            stream_subject = f"{self._settings.arc_nats_stream_prefix}.{request_id}"
            first_token = True
            ttft_ms = 0
            latency_ms = 0

            async for chunk in stream_graph(self._graph, self._memory, user_id, text):
                if first_token:
                    ttft_ms = int((time.monotonic() - start) * 1000)
                    self._metrics.ttft_seconds.record(ttft_ms / 1000, {"transport": "nats"})
                    first_token = False

                chunk_payload = json.dumps({"request_id": request_id, "chunk": chunk})
                if self._nc is not None:
                    await self._nc.publish(stream_subject, chunk_payload.encode())

            latency_ms = int((time.monotonic() - start) * 1000)
            self._metrics.latency.record(latency_ms, {"transport": "nats"})

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

            # Legacy request-reply support: respond directly if reply subject set
            if msg.reply:
                await msg.respond(completion_payload.encode())

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
