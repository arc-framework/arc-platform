from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from sherlock.graph import invoke_graph
from sherlock.interfaces import ModelRegistryPort, StreamingPort
from sherlock.models_v1 import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ResponseInputItem,
    ResponseOutputContent,
    ResponseOutputItem,
    ResponsesRequest,
    ResponsesResponse,
    ResponsesUsage,
    UsageInfo,
)

_log = structlog.get_logger(__name__)


def _derive_user_id(messages: list[ChatMessage]) -> str:
    """UUID v5 from joined user message content — stable across identical requests."""
    content = "|".join(m.content or "" for m in messages if m.role == "user")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, content))


def build_openai_router(
    registry: ModelRegistryPort,
    streaming_adapter: StreamingPort,
) -> APIRouter:
    """Return an APIRouter with POST /chat/completions and POST /responses.

    Mount with prefix=/v1 in main.py.
    """
    router = APIRouter(tags=["chat"])

    @router.post("/chat/completions", response_model=None)
    async def chat_completions(
        req: ChatCompletionRequest, request: Request
    ) -> ChatCompletionResponse | JSONResponse | EventSourceResponse:
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"detail": "Service not ready"}, status_code=503)

        if not registry.model_exists(req.model):
            return JSONResponse(
                {"error": {"type": "invalid_request_error", "code": "model_not_found"}},
                status_code=404,
            )

        graph = state.graph
        memory = state.memory
        metrics = state.metrics
        user_id = req.user or _derive_user_id(req.messages)

        metrics.v1_requests_total.add(1, {"transport": "http", "stream": str(req.stream)})

        _log.debug(
            "v1 chat request",
            event_type="service_call",
            model=req.model,
            user_id=user_id,
            message_count=len(req.messages),
            stream=req.stream,
        )

        if req.stream:
            adapter = streaming_adapter

            async def _generate() -> AsyncGenerator[str]:
                chunk_count = 0
                async for chunk in adapter.stream(req):
                    chunk_count += 1
                    yield chunk.model_dump_json()
                metrics.v1_stream_chunks.add(chunk_count, {"transport": "http"})
                yield "[DONE]"

            return EventSourceResponse(_generate())

        # Synchronous path
        text = next(
            (m.content or "" for m in reversed(req.messages) if m.role == "user"),
            "",
        )
        start = time.monotonic()
        try:
            response_text = await invoke_graph(graph, memory, user_id, text)
            latency_ms = int((time.monotonic() - start) * 1000)
            metrics.v1_latency.record(latency_ms, {"transport": "http"})
            _log.debug(
                "v1 chat done",
                event_type="service_call",
                model=req.model,
                user_id=user_id,
                latency_ms=latency_ms,
            )
            return ChatCompletionResponse(
                model=req.model,
                choices=[Choice(message=ChatMessage(role="assistant", content=response_text))],
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            )
        except Exception as exc:
            metrics.v1_errors_total.add(1, {"transport": "http"})
            _log.error(
                "v1 chat error",
                event_type="exception",
                error_type=type(exc).__name__,
                model=req.model,
            )
            return JSONResponse(
                {"error": {"type": "server_error", "message": str(exc)}},
                status_code=500,
            )

    @router.post("/responses", response_model=None)
    async def responses(
        req: ResponsesRequest, request: Request
    ) -> ResponsesResponse | JSONResponse:
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"detail": "Service not ready"}, status_code=503)

        if not registry.model_exists(req.model):
            return JSONResponse(
                {"error": {"type": "invalid_request_error", "code": "model_not_found"}},
                status_code=404,
            )

        graph = state.graph
        memory = state.memory
        metrics = state.metrics
        user_id = req.user or str(uuid.uuid4())

        # Normalize input to plain text
        if isinstance(req.input, str):
            text = req.input
        else:
            items: list[ResponseInputItem] = req.input
            text = next(
                (item.content for item in reversed(items) if item.role == "user"),
                "",
            )

        start = time.monotonic()
        metrics.v1_requests_total.add(1, {"transport": "http", "stream": "false"})

        try:
            response_text = await invoke_graph(graph, memory, user_id, text)
            latency_ms = int((time.monotonic() - start) * 1000)
            metrics.v1_latency.record(latency_ms, {"transport": "http"})
            return ResponsesResponse(
                model=req.model,
                output=[
                    ResponseOutputItem(
                        content=[ResponseOutputContent(text=response_text)]
                    )
                ],
                usage=ResponsesUsage(input_tokens=0, output_tokens=0, total_tokens=0),
                instructions=req.instructions,
            )
        except Exception as exc:
            metrics.v1_errors_total.add(1, {"transport": "http"})
            _log.error(
                "v1 responses error",
                event_type="exception",
                error_type=type(exc).__name__,
                model=req.model,
            )
            return JSONResponse(
                {"error": {"type": "server_error", "message": str(exc)}},
                status_code=500,
            )

    return router
