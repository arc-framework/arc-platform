"""FastAPI router for POST /v1/audio/transcriptions."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse

from voice.config import Settings
from voice.interfaces import STTError, STTPort, TranscriptResult
from voice.models_v1 import ErrorResponse, TranscriptionResponse
from voice.observability import get_stt_histogram, get_tracer

router = APIRouter()

# ─── Module-level singleton (lazy-initialised) ───────────────────────────────

_stt_adapter: STTPort | None = None


def _get_stt_adapter() -> STTPort:
    """Return the module-level STT adapter, creating it on first call."""
    global _stt_adapter
    if _stt_adapter is None:
        from voice.providers.stt_whisper import WhisperSTTAdapter

        settings = Settings()
        _stt_adapter = WhisperSTTAdapter(
            model=settings.whisper_model,
            device=settings.whisper_device,
        )
    return _stt_adapter


# ─── Route ────────────────────────────────────────────────────────────────────


@router.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile,
    stt: Annotated[STTPort, Depends(_get_stt_adapter)],
) -> JSONResponse:
    """Transcribe an uploaded audio file.

    Accepts any audio/* MIME type.  Rejects anything else with 400.
    Returns ``TranscriptionResponse`` JSON on success or ``ErrorResponse`` JSON
    on provider failure (502).
    """
    correlation_id = str(uuid.uuid4())

    # ── MIME validation ───────────────────────────────────────────────────────
    content_type = file.content_type or ""
    if not content_type.startswith("audio/"):
        error = ErrorResponse(
            error_type="invalid_input",
            message=f"Unsupported content type: {content_type!r}. Expected audio/*.",
            correlation_id=correlation_id,
        )
        return JSONResponse(status_code=400, content=error.model_dump())

    audio_bytes = await file.read()

    # ── OTEL span + histogram ─────────────────────────────────────────────────
    tracer = get_tracer()
    histogram = get_stt_histogram()

    with tracer.start_as_current_span("stt.transcribe") as span:
        span.set_attribute("stt.bytes", len(audio_bytes))
        span.set_attribute("stt.content_type", content_type)
        span.set_attribute("stt.correlation_id", correlation_id)

        t0 = time.perf_counter()
        try:
            result: TranscriptResult = await stt.transcribe(audio_bytes)
        except STTError as exc:
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

    response = TranscriptionResponse(
        text=result.text,
        language=result.language,
        duration=result.duration_secs,
    )
    return JSONResponse(status_code=200, content=response.model_dump())
