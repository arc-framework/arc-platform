"""FastAPI application factory and lifespan for arc-voice-agent (Scarlett).

Wiring order on startup:
  1. Telemetry (OTEL) — must be first; histograms used by routers
  2. NATS connection — shared singleton used by NATSBridge
  3. Pulsar publisher — fire-and-forget event bus
  4. Adapters + worker — hexagonal wiring of STT / TTS / bridge
  5. Worker background task — launched via asyncio.create_task()

Shutdown order (5 s timeout on worker, then fail-open):
  worker → Pulsar → NATS
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from voice.config import Settings
from voice.health_router import router as health_router
from voice.livekit_worker import VoiceAgentWorker
from voice.nats_bridge import NATSBridge
from voice.nats_bridge import connect as nats_connect
from voice.nats_bridge import disconnect as nats_disconnect
from voice.observability import setup_telemetry
from voice.providers.stt_whisper import WhisperSTTAdapter
from voice.providers.tts_piper import PiperTTSAdapter
from voice.pulsar_events import VoiceEventPublisher
from voice.stt_router import router as stt_router
from voice.tts_router import router as tts_router

_log = logging.getLogger(__name__)

_WORKER_SHUTDOWN_TIMEOUT_S = 5.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: UP043
    """Manage startup and ordered shutdown of all voice service resources."""
    settings = Settings()

    # 1. Telemetry must be first — routers call get_tracer() / histograms
    setup_telemetry(settings)

    # 2. NATS — shared singleton used by NATSBridge.reason()
    await nats_connect(settings.nats_url)

    # 3. Pulsar publisher — fail-open; unavailability is logged, not raised
    publisher = VoiceEventPublisher()
    publisher.connect(settings.pulsar_url)

    # 4. Build concrete adapters and wire the worker
    stt = WhisperSTTAdapter(model=settings.whisper_model, device=settings.whisper_device)
    tts = PiperTTSAdapter(piper_bin=settings.piper_bin)
    bridge = NATSBridge(
        subject=settings.bridge_nats_subject,
        timeout_ms=settings.bridge_timeout_ms,
    )
    worker = VoiceAgentWorker(
        stt=stt,
        tts=tts,
        bridge=bridge,
        publisher=publisher,
        settings=settings,
    )

    # 5. Launch worker as a background task
    worker_task = asyncio.create_task(worker.run())

    yield  # --- app is running ---

    # Shutdown — ordered teardown
    await worker.stop()
    try:
        await asyncio.wait_for(worker_task, timeout=_WORKER_SHUTDOWN_TIMEOUT_S)
    except TimeoutError:
        _log.error(
            "voice worker did not stop within %.1f s — cancelling",
            _WORKER_SHUTDOWN_TIMEOUT_S,
        )
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task

    publisher.disconnect()
    await nats_disconnect()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional pre-built Settings (reserved for future DI patterns).
            The lifespan handler always constructs its own Settings() instance.

    Returns:
        Configured FastAPI instance with STT, TTS, and health routers mounted.
    """
    app = FastAPI(
        title="arc-voice-agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(stt_router)
    app.include_router(tts_router)
    app.include_router(health_router)

    return app


app = create_app()
