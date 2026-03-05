from __future__ import annotations

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
from reasoner.models_v1 import (
    ChatCompletionRequest,
    ChatMessage,
)
from reasoner.observability import SherlockMetrics

_log = structlog.get_logger(__name__)


def _derive_user_id(messages: list[ChatMessage]) -> str:
    """UUID v5 from joined user message content — stable across identical requests."""
    content = "|".join(m.content or "" for m in messages if m.role == "user")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, content))


class OpenAINATSHandler:
    """NATS v1 chat handler — subscribes to reasoner.v1.chat, streams tokens via arc.* subjects.

    Mirrors NATSHandler but uses ChatCompletionRequest wire format.
    Token chunks are published to arc.reasoner.stream.{request_id}.
    Completion signal is published to arc.reasoner.result.
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
        """Subscribe to the v1 chat subject with queue group load balancing."""
        if self._nc is None:
            raise RuntimeError("OpenAINATSHandler.connect() must be called before subscribe()")
        await self._nc.subscribe(
            self._settings.nats_v1_chat_subject,
            queue=self._settings.nats_queue_group,
            cb=self._handle,
        )

    async def _handle(self, msg: Msg) -> None:
        """Process an incoming v1 chat NATS message using stream_graph() for token streaming.

        Publishes token chunks to arc.reasoner.stream.{request_id}.
        Sends completion signal to arc.reasoner.result.
        Records ttft_seconds from request receive to first token emitted.
        """
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        self._metrics.v1_requests_total.add(1, {"transport": "nats"})

        req: ChatCompletionRequest | None = None
        try:
            req = ChatCompletionRequest.model_validate_json(msg.data)
            user_id = req.user or _derive_user_id(req.messages)
            _log.debug(
                "nats v1 recv",
                event_type="message_received",
                subject=msg.subject,
                transport="nats",
                model=req.model,
                user_id=user_id,
                request_id=request_id,
            )

            text = next(
                (m.content or "" for m in reversed(req.messages) if m.role == "user"),
                None,
            )
            if text is None:
                raise ValueError("No user message found in ChatCompletionRequest.messages")

            stream_subject = f"{self._settings.arc_nats_stream_prefix}.{request_id}"
            first_token = True
            ttft_ms = 0

            async for chunk in stream_graph(self._graph, self._memory, user_id, text):
                if first_token:
                    ttft_ms = int((time.monotonic() - start) * 1000)
                    self._metrics.ttft_seconds.record(ttft_ms / 1000, {"transport": "nats"})
                    first_token = False

                chunk_payload = json.dumps({"request_id": request_id, "chunk": chunk})
                if self._nc is not None:
                    await self._nc.publish(stream_subject, chunk_payload.encode())

            latency_ms = int((time.monotonic() - start) * 1000)
            self._metrics.v1_latency.record(latency_ms, {"transport": "nats"})

            completion_payload = json.dumps({
                "request_id": request_id,
                "user_id": user_id,
                "model": req.model,
                "done": True,
                "ttft_ms": ttft_ms,
                "latency_ms": latency_ms,
            })
            if self._nc is not None:
                await self._nc.publish(
                    self._settings.arc_nats_result_subject,
                    completion_payload.encode(),
                )
                # Also publish to legacy v1 result subject for existing consumers
                await self._nc.publish(
                    self._settings.nats_v1_result_subject,
                    completion_payload.encode(),
                )

            if msg.reply:
                await msg.respond(completion_payload.encode())

        except Exception as exc:
            self._metrics.v1_errors_total.add(1, {"transport": "nats"})
            latency_ms = int((time.monotonic() - start) * 1000)
            model = req.model if req is not None else "unknown"
            _log.error(
                "nats v1 error",
                event_type="exception",
                error=str(exc),
                transport="nats",
                model=model,
                latency_ms=latency_ms,
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
        """Return True if the NATS connection is active, or if v1 NATS is disabled."""
        if not self._settings.nats_v1_enabled:
            return True
        return self._nc is not None and self._nc.is_connected

    async def close(self) -> None:
        """Drain and close the NATS connection."""
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
            self._nc = None
