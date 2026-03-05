from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import structlog

from reasoner.graph import stream_graph
from reasoner.memory import SherlockMemory
from reasoner.models_v1 import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatMessage,
    ChoiceDelta,
    StreamChoice,
    UsageInfo,
)

_log = structlog.get_logger(__name__)


def _derive_user_id(messages: list[ChatMessage]) -> str:
    """UUID v5 from joined user message content — stable across identical requests."""
    content = "|".join(m.content or "" for m in messages if m.role == "user")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, content))


class GraphStreamingAdapter:
    """Implements StreamingPort — wraps stream_graph() into ChatCompletionChunk SSE events."""

    def __init__(self, graph: Any, memory: SherlockMemory) -> None:
        self._graph = graph
        self._memory = memory

    def stream(self, req: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        """Return async iterator of SSE chunks. Sync wrapper calls the async generator."""
        user_id = req.user or _derive_user_id(req.messages)
        text = next(
            (m.content or "" for m in reversed(req.messages) if m.role == "user"),
            "",
        )
        _log.debug(
            "stream_start",
            model=req.model,
            user_id=user_id,
        )
        return self._stream_tokens(req.model, user_id, text)

    async def _stream_tokens(
        self,
        model: str,
        user_id: str,
        text: str,
    ) -> AsyncGenerator[ChatCompletionChunk]:
        """Async generator: yields ChatCompletionChunk for each token, then finish chunk."""
        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())

        async for token in stream_graph(self._graph, self._memory, user_id, text):
            yield ChatCompletionChunk(
                id=chunk_id,
                created=created,
                model=model,
                choices=[
                    StreamChoice(
                        delta=ChoiceDelta(content=token),
                        finish_reason=None,
                    )
                ],
            )

        # Final chunk signals stream end
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=model,
            choices=[
                StreamChoice(
                    delta=ChoiceDelta(content=None),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

