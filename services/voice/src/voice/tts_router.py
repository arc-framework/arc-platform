"""FastAPI router for POST /v1/audio/speech."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response, StreamingResponse

from voice.config import Settings
from voice.interfaces import TTSError, TTSPort
from voice.models_v1 import ErrorResponse, SpeechRequest
from voice.observability import get_tracer, get_tts_histogram

router = APIRouter()

# ─── Module-level singleton (lazy-initialised) ───────────────────────────────

_tts_adapter: TTSPort | None = None


def _get_tts_adapter() -> TTSPort:
    """Return the module-level TTS adapter, creating it on first call."""
    global _tts_adapter
    if _tts_adapter is None:
        from voice.providers.tts_piper import PiperTTSAdapter

        settings = Settings()
        _tts_adapter = PiperTTSAdapter(piper_bin=settings.piper_bin)
    return _tts_adapter


# ─── Route ────────────────────────────────────────────────────────────────────


@router.post("/v1/audio/speech", response_model=None)
async def synthesize_speech(
    request: SpeechRequest,
    tts: Annotated[TTSPort, Depends(_get_tts_adapter)],
) -> Response:
    """Synthesize speech from text input.

    Returns a WAV audio stream with ``Content-Type: audio/wav``,
    ``X-Duration-Seconds``, and ``X-Sample-Rate`` headers.

    Returns ``ErrorResponse`` JSON on validation failure (400) or provider
    failure (502).
    """
    correlation_id = str(uuid.uuid4())

    # ── Input validation ──────────────────────────────────────────────────────
    if not request.input.strip():
        error = ErrorResponse(
            error_type="invalid_input",
            message="'input' must not be empty.",
            correlation_id=correlation_id,
        )
        return JSONResponse(status_code=400, content=error.model_dump())

    # ── OTEL span + histogram ─────────────────────────────────────────────────
    tracer = get_tracer()
    histogram = get_tts_histogram()

    with tracer.start_as_current_span("tts.synthesize") as span:
        span.set_attribute("tts.input_length", len(request.input))
        span.set_attribute("tts.voice", request.voice)
        span.set_attribute("tts.correlation_id", correlation_id)

        t0 = time.perf_counter()
        try:
            result = await tts.synthesize(request.input, request.voice)
        except TTSError as exc:
            span.record_exception(exc)
            error = ErrorResponse(
                error_type="provider_unavailable",
                message=str(exc),
                correlation_id=correlation_id,
            )
            return JSONResponse(status_code=502, content=error.model_dump())
        finally:
            latency = time.perf_counter() - t0
            histogram.record(latency)

    headers = {
        "X-Duration-Seconds": str(result.duration_secs),
        "X-Sample-Rate": str(result.sample_rate),
    }

    return StreamingResponse(
        content=iter([result.wav_bytes]),
        media_type="audio/wav",
        headers=headers,
    )
