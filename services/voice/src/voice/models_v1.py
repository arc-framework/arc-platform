from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ─── REST I/O Models ──────────────────────────────────────────────────────────


class TranscriptionRequest(BaseModel):
    """Documents expected multipart form fields for POST /v1/audio/transcriptions."""

    model: str
    language: str | None = None


class TranscriptionResponse(BaseModel):
    """OpenAI-compatible transcription response."""

    text: str
    language: str
    duration: float


class SpeechRequest(BaseModel):
    """Request body for POST /v1/audio/speech."""

    model: str
    input: str
    voice: str = "default"
    response_format: str = "wav"


# ─── Error Model (GAP-1) ──────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Typed error response used by STT and TTS routers for 400/502 responses."""

    error_type: Literal["unsupported_format", "provider_unavailable", "invalid_input"]
    message: str
    correlation_id: str


# ─── Health Models (GAP-2) ────────────────────────────────────────────────────


class HealthCheckDetail(BaseModel):
    """Per-dependency health check detail."""

    status: Literal["ok", "degraded", "unhealthy"]
    reason: str | None = None
    latency_ms: float | None = None


class HealthCheckResponse(BaseModel):
    """Response body for GET /health/deep."""

    status: Literal["ok", "degraded", "unhealthy"]
    checks: dict[str, HealthCheckDetail]


# ─── Durable Event Base ───────────────────────────────────────────────────────


class _VoiceEventBase(BaseModel):
    """Shared fields for all voice lifecycle events published to arc.voice.* topics."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    room_id: str
    correlation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ─── Voice Session Events ─────────────────────────────────────────────────────


class VoiceSessionStartedEvent(_VoiceEventBase):
    """Published to arc.voice.session.started when a participant joins a room."""

    participant_identity: str


class VoiceSessionEndedEvent(_VoiceEventBase):
    """Published to arc.voice.session.ended when a session concludes."""

    duration_secs: float


# ─── Voice Turn Events ────────────────────────────────────────────────────────


class VoiceTurnCompletedEvent(_VoiceEventBase):
    """Published to arc.voice.turn.completed after a full STT → bridge → TTS pipeline."""

    transcript: str
    # First 200 chars of the LLM response — no raw audio bytes ever stored in events.
    response_preview: str
    stt_latency_ms: float
    bridge_latency_ms: float
    tts_latency_ms: float
    total_latency_ms: float


class VoiceTurnFailedEvent(_VoiceEventBase):
    """Published to arc.voice.turn.failed when any stage of the pipeline errors."""

    error_type: Literal["stt_error", "bridge_timeout", "bridge_error", "tts_error", "unknown"]
    error_message: str
