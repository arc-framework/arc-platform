from __future__ import annotations

import asyncio
import time

import structlog
import tiktoken
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from opentelemetry import metrics
from pydantic import BaseModel

_log = structlog.get_logger(__name__)

_meter = metrics.get_meter("arc-sherlock")
_embed_latency = _meter.create_histogram(
    "sherlock.rag.embed.latency",
    description="Embedding request latency in milliseconds",
    unit="ms",
)

router = APIRouter(tags=["embeddings"])


class EmbeddingRequest(BaseModel):
    model: str = "text-embedding-ada-002"
    input: str | list[str]
    encoding_format: str = "float"


@router.post("/embeddings", response_model=None)
async def create_embeddings(
    req: EmbeddingRequest, request: Request
) -> JSONResponse:
    """OpenAI-compatible embeddings endpoint backed by the shared EmbedderAdapter."""
    try:
        state = request.app.state.app_state
    except AttributeError:
        return JSONResponse({"detail": "Service not ready"}, status_code=503)

    if getattr(state, "rag", None) is None:
        return JSONResponse({"error": "RAG not enabled"}, status_code=503)

    texts: list[str] = [req.input] if isinstance(req.input, str) else list(req.input)

    start = time.perf_counter()
    embeddings: list[list[float]] = await asyncio.to_thread(
        state.rag.embedder.encode, texts
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    _embed_latency.record(latency_ms)

    enc = tiktoken.get_encoding("cl100k_base")
    prompt_tokens = sum(len(enc.encode(t)) for t in texts)

    _log.debug(
        "embeddings.done",
        event_type="service_call",
        model=req.model,
        input_count=len(texts),
        prompt_tokens=prompt_tokens,
        latency_ms=latency_ms,
    )

    data = [
        {"object": "embedding", "index": i, "embedding": emb}
        for i, emb in enumerate(embeddings)
    ]
    return JSONResponse({
        "object": "list",
        "data": data,
        "model": req.model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens,
        },
    })
