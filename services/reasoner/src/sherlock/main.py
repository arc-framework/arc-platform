from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog
from faker import Faker
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from sherlock.config import Settings
from sherlock.graph import GraphErrorResponse, build_graph, invoke_graph
from sherlock.llm_factory import create_llm
from sherlock.memory import SherlockMemory
from sherlock.models_router import StaticModelRegistry, build_models_router
from sherlock.nats_handler import NATSHandler
from sherlock.observability import (
    SherlockMetrics,
    configure_logging,
    init_telemetry,
    instrument_app,
)
from sherlock.openai_nats_handler import OpenAINATSHandler
from sherlock.openai_router import build_openai_router
from sherlock.pulsar_handler import PulsarHandler
from sherlock.streaming import GraphStreamingAdapter

logger = structlog.get_logger(__name__)


# ─── Request / Response models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty")
        return v


class ChatResponse(BaseModel):
    user_id: str
    text: str
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    version: str


class DeepHealthResponse(BaseModel):
    status: str
    version: str
    components: dict[str, bool]


# ─── AppState (no module-level singletons) ────────────────────────────────────

@dataclass
class AppState:
    """All service singletons live here — initialized exclusively inside lifespan."""

    memory: SherlockMemory
    graph: Any
    nats: NATSHandler
    metrics: SherlockMetrics
    pulsar: PulsarHandler | None = field(default=None)
    openai_nats: OpenAINATSHandler | None = field(default=None)
    model_registry: StaticModelRegistry | None = field(default=None)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup / shutdown sequence — all singletons created here, never at module scope."""
    settings = Settings()

    configure_logging()
    init_telemetry(settings)

    log = structlog.get_logger("sherlock.startup")
    log.info("starting", version=settings.service_version)

    if settings.dev_mode:
        app.include_router(_dev_router)
        log.warning("dev_mode enabled — /fake/* endpoints are active")

    memory = SherlockMemory(settings)
    await memory.init()

    llm, supports_system_role = create_llm(settings)
    graph = build_graph(
        memory,
        llm,
        supports_system_role=supports_system_role,
        system_prompt=settings.system_prompt,
    )

    metrics = SherlockMetrics()

    nats_handler = NATSHandler(graph, memory, settings, metrics)
    if settings.nats_enabled:
        await nats_handler.connect()
        await nats_handler.subscribe()

    pulsar_handler: PulsarHandler | None = None
    if settings.pulsar_enabled:
        pulsar_handler = PulsarHandler(graph, memory, settings, metrics)
        await pulsar_handler.start()

    # StaticModelRegistry — registered model for /v1/models
    model_registry = StaticModelRegistry(settings)

    # GraphStreamingAdapter — wraps stream_graph for SSE
    streaming_adapter = GraphStreamingAdapter(graph, memory)

    # OpenAINATSHandler — v1 NATS channel
    openai_nats_handler: OpenAINATSHandler | None = None
    if settings.nats_v1_enabled and settings.nats_enabled:
        openai_nats_handler = OpenAINATSHandler(graph, memory, settings, metrics)
        await openai_nats_handler.connect()
        await openai_nats_handler.subscribe()

    app.include_router(build_openai_router(model_registry, streaming_adapter), prefix="/v1")
    app.include_router(build_models_router(model_registry), prefix="/v1")

    if settings.async_docs_enabled:
        import os

        from fastapi.staticfiles import StaticFiles

        async_docs_dir = "/app/async-docs"
        if os.path.isdir(async_docs_dir):
            app.mount(
                "/async-docs",
                StaticFiles(directory=async_docs_dir, html=True),
                name="async-docs",
            )
            log.info("async_docs mounted", path=async_docs_dir)
        else:

            @app.get("/async-docs", tags=["docs"])
            async def async_docs_not_available() -> JSONResponse:
                return JSONResponse(
                    {"detail": "AsyncAPI docs not available — run via Docker to generate UI"},
                    status_code=404,
                )

    app.state.app_state = AppState(
        memory=memory,
        graph=graph,
        nats=nats_handler,
        metrics=metrics,
        pulsar=pulsar_handler,
        openai_nats=openai_nats_handler,
        model_registry=model_registry,
    )

    log.info("ready", port=8000)
    yield

    # ── Shutdown ──
    log.info("shutting_down")
    await nats_handler.close()
    if pulsar_handler is not None:
        await pulsar_handler.close()
    if openai_nats_handler is not None:
        await openai_nats_handler.close()


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="arc-sherlock",
    description="LangGraph reasoning engine — pgvector memory, NATS/Pulsar transports",
    version="0.1.0",
    lifespan=lifespan,
)

instrument_app(app)

_request_log = structlog.get_logger("sherlock.http")


@app.middleware("http")
async def request_logger(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.monotonic()
    response = await call_next(request)
    latency_ms = int((time.monotonic() - start) * 1000)
    _request_log.info(
        f"{request.method} {request.url.path} {response.status_code} {latency_ms}ms",
        event_type="http_request",
        method=request.method,
        path=str(request.url.path),
        status=response.status_code,
        latency_ms=latency_ms,
    )
    return response


# ─── Dev-only faker router ────────────────────────────────────────────────────

_fake = Faker()

_dev_router = APIRouter(prefix="/fake", tags=["dev"])


@_dev_router.get("/chat", summary="Generate a fake /chat request body")
async def fake_chat_body() -> dict[str, str]:
    """Returns a randomised ChatRequest payload ready to POST to /chat."""
    return {
        "user_id": _fake.uuid4(),
        "text": _fake.sentence(nb_words=10),
    }


@_dev_router.get("/chat/batch", summary="Generate N fake /chat request bodies")
async def fake_chat_batch(n: int = 5) -> list[dict[str, str]]:
    """Returns a list of N randomised ChatRequest payloads (max 20)."""
    count = min(n, 20)
    return [{"user_id": _fake.uuid4(), "text": _fake.sentence(nb_words=10)} for _ in range(count)]


# ─── Dependency helper ────────────────────────────────────────────────────────

def _get_state(request: Request) -> AppState:
    state: AppState = request.app.state.app_state
    return state


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Synchronous HTTP reasoning endpoint."""
    try:
        state = _get_state(request)
    except AttributeError:
        raise HTTPException(status_code=503, detail="Service not ready") from None

    if state.graph is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    state.metrics.requests_total.add(1, {"transport": "http"})
    start = time.monotonic()

    try:
        response_text = await invoke_graph(
            state.graph, state.memory, body.user_id, body.text
        )
    except GraphErrorResponse as graph_err:
        # Graph returned graceful error (error_handler exhausted retries).
        # HTTP callers receive the error message as `text` — still a 200 response
        # since the message was fully processed. Distinguish via content if needed.
        state.metrics.errors_total.add(1, {"transport": "http"})
        latency_ms = int((time.monotonic() - start) * 1000)
        state.metrics.latency.record(latency_ms, {"transport": "http"})
        return ChatResponse(
            user_id=body.user_id,
            text=graph_err.error_message,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        state.metrics.errors_total.add(1, {"transport": "http"})
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency_ms = int((time.monotonic() - start) * 1000)
    state.metrics.latency.record(latency_ms, {"transport": "http"})

    return ChatResponse(
        user_id=body.user_id,
        text=response_text,
        latency_ms=latency_ms,
    )


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Shallow liveness probe — always fast, never calls deps."""
    try:
        state = _get_state(request)
        nats_ok = state.nats.is_connected()
    except AttributeError:
        nats_ok = False

    if not nats_ok:
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={"status": "starting", "version": "0.1.0"},
        )

    return HealthResponse(status="ok", version="0.1.0")


@app.get("/health/deep", response_model=DeepHealthResponse)
async def health_deep(request: Request) -> DeepHealthResponse:
    """Readiness probe — checks all dependencies; returns 503 if any are degraded."""
    try:
        state = _get_state(request)
    except AttributeError:
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={
                "status": "not_ready",
                "version": "0.1.0",
                "components": {"postgres": False, "nats": False},
            },
        )

    dep_health = await state.memory.health_check()
    components = {
        "postgres": dep_health.get("postgres", False),
        "nats": state.nats.is_connected(),
    }

    all_healthy = all(components.values())
    status_code = 200 if all_healthy else 503
    body = DeepHealthResponse(
        status="ok" if all_healthy else "degraded",
        version="0.1.0",
        components=components,
    )

    if not all_healthy:
        return JSONResponse(  # type: ignore[return-value]
            status_code=status_code,
            content=body.model_dump(),
        )

    return body
