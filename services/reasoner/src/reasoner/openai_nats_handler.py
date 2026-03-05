from __future__ import annotations

import time
import uuid
from typing import Any

import nats
import structlog
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from reasoner.config import Settings
from reasoner.graph import invoke_graph
from reasoner.models_v1 import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    UsageInfo,
)
from reasoner.observability import SherlockMetrics

_log = structlog.get_logger(__name__)


def _derive_user_id(messages: list[ChatMessage]) -> str:
    """UUID v5 from joined user message content — stable across identical requests."""
    content = "|".join(m.content or "" for m in messages if m.role == "user")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, content))


class OpenAINATSHandler:
    """NATS v1 chat handler — subscribes to reasoner.v1.chat, publishes to reasoner.v1.result.

    Mirrors NATSHandler but uses ChatCompletionRequest/Response wire format.
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
        """Process an incoming v1 chat NATS message and publish a ChatCompletionResponse."""
        start = time.monotonic()
        self._metrics.v1_requests_total.add(1, {"transport": "nats"})

        req: ChatCompletionRequest | None = None
        try:
            req = ChatCompletionRequest.model_validate_json(msg.data)
            user_id = req.user or _derive_user_id(req.messages)
            _log.debug(
                f"nats v1 recv: {msg.subject}",
                event_type="message_received",
                subject=msg.subject,
                transport="nats",
                model=req.model,
                user_id=user_id,
            )

            text = next(
                (m.content or "" for m in reversed(req.messages) if m.role == "user"),
                None,
            )
            if text is None:
                raise ValueError("No user message found in ChatCompletionRequest.messages")

            response_text = await invoke_graph(self._graph, self._memory, user_id, text)
            latency_ms = int((time.monotonic() - start) * 1000)
            self._metrics.v1_latency.record(latency_ms, {"transport": "nats"})

            result = ChatCompletionResponse(
                model=req.model,
                choices=[
                    Choice(message=ChatMessage(role="assistant", content=response_text))
                ],
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            )

        except Exception as exc:
            self._metrics.v1_errors_total.add(1, {"transport": "nats"})
            latency_ms = int((time.monotonic() - start) * 1000)
            model = req.model if req is not None else "unknown"
            _log.error(
                f"nats v1 error: {type(exc).__name__}",
                event_type="exception",
                error=str(exc),
                transport="nats",
                model=model,
                latency_ms=latency_ms,
            )
            result = ChatCompletionResponse(
                model=model,
                choices=[
                    Choice(
                        message=ChatMessage(
                            role="assistant", content="Error: internal server error"
                        ),
                        finish_reason=None,
                    )
                ],
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            )

        result_bytes = result.model_dump_json().encode()
        if self._nc is not None:
            if msg.reply:
                await msg.respond(result_bytes)
            await self._nc.publish(self._settings.nats_v1_result_subject, result_bytes)

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
