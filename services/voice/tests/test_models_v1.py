from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from voice.models_v1 import (
    ErrorResponse,
    HealthCheckDetail,
    HealthCheckResponse,
    SpeechRequest,
    TranscriptionRequest,
    TranscriptionResponse,
    VoiceSessionEndedEvent,
    VoiceSessionStartedEvent,
    VoiceTurnCompletedEvent,
    VoiceTurnFailedEvent,
)

# ─── REST I/O Models ──────────────────────────────────────────────────────────


class TestTranscriptionRequest:
    def test_instantiates_with_valid_data(self) -> None:
        req = TranscriptionRequest(model="whisper-1", language="en")
        assert req.model == "whisper-1"
        assert req.language == "en"

    def test_language_defaults_to_none(self) -> None:
        req = TranscriptionRequest(model="whisper-1")
        assert req.language is None


class TestTranscriptionResponse:
    def test_openai_compatible_fields(self) -> None:
        resp = TranscriptionResponse(text="Hello world", language="en", duration=1.23)
        assert resp.text == "Hello world"
        assert resp.language == "en"
        assert resp.duration == pytest.approx(1.23)

    def test_required_fields_missing_raises(self) -> None:
        with pytest.raises(ValidationError):
            TranscriptionResponse(text="hi")  # type: ignore[call-arg]


class TestSpeechRequest:
    def test_defaults(self) -> None:
        req = SpeechRequest(model="tts-1", input="Hello", voice="default")
        assert req.voice == "default"
        assert req.response_format == "wav"

    def test_custom_values(self) -> None:
        req = SpeechRequest(model="tts-1", input="Hi", voice="nova", response_format="mp3")
        assert req.voice == "nova"
        assert req.response_format == "mp3"

    def test_required_fields_missing_raises(self) -> None:
        with pytest.raises(ValidationError):
            SpeechRequest(voice="nova")  # type: ignore[call-arg]


# ─── Error Model ──────────────────────────────────────────────────────────────


class TestErrorResponse:
    def test_valid_error_type_unsupported_format(self) -> None:
        err = ErrorResponse(
            error_type="unsupported_format",
            message="Only WAV and FLAC are accepted",
            correlation_id="corr-123",
        )
        assert err.error_type == "unsupported_format"

    def test_valid_error_type_provider_unavailable(self) -> None:
        err = ErrorResponse(
            error_type="provider_unavailable",
            message="Whisper failed",
            correlation_id="corr-456",
        )
        assert err.error_type == "provider_unavailable"

    def test_valid_error_type_invalid_input(self) -> None:
        err = ErrorResponse(
            error_type="invalid_input",
            message="Empty input",
            correlation_id="corr-789",
        )
        assert err.error_type == "invalid_input"

    def test_invalid_error_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ErrorResponse(
                error_type="bad_type",  # type: ignore[arg-type]
                message="oops",
                correlation_id="corr-000",
            )


# ─── Health Models ────────────────────────────────────────────────────────────


class TestHealthCheckDetail:
    def test_ok_status_no_reason(self) -> None:
        detail = HealthCheckDetail(status="ok")
        assert detail.status == "ok"
        assert detail.reason is None
        assert detail.latency_ms is None

    def test_degraded_with_reason_and_latency(self) -> None:
        detail = HealthCheckDetail(status="degraded", reason="timeout", latency_ms=250.0)
        assert detail.status == "degraded"
        assert detail.reason == "timeout"
        assert detail.latency_ms == pytest.approx(250.0)

    def test_unhealthy_status(self) -> None:
        detail = HealthCheckDetail(status="unhealthy", reason="connection refused")
        assert detail.status == "unhealthy"

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            HealthCheckDetail(status="unknown")  # type: ignore[arg-type]


class TestHealthCheckResponse:
    def test_ok_response(self) -> None:
        resp = HealthCheckResponse(
            status="ok",
            checks={
                "nats": HealthCheckDetail(status="ok"),
                "livekit": HealthCheckDetail(status="ok"),
            },
        )
        assert resp.status == "ok"
        assert len(resp.checks) == 2

    def test_degraded_response(self) -> None:
        resp = HealthCheckResponse(
            status="degraded",
            checks={
                "nats": HealthCheckDetail(status="ok", latency_ms=5.0),
                "livekit": HealthCheckDetail(
                    status="degraded", reason="high latency", latency_ms=800.0
                ),
            },
        )
        assert resp.status == "degraded"
        assert resp.checks["livekit"].status == "degraded"

    def test_empty_checks_allowed(self) -> None:
        resp = HealthCheckResponse(status="ok", checks={})
        assert resp.checks == {}


# ─── Event Models ─────────────────────────────────────────────────────────────

_NOW = datetime.now(UTC)
_BASE = {
    "session_id": "sess-abc",
    "room_id": "room-xyz",
    "correlation_id": "corr-111",
    "timestamp": _NOW,
}


class TestVoiceSessionStartedEvent:
    def test_instantiates_with_required_fields(self) -> None:
        event = VoiceSessionStartedEvent(**_BASE, participant_identity="user-42")
        assert event.session_id == "sess-abc"
        assert event.room_id == "room-xyz"
        assert event.participant_identity == "user-42"
        assert event.timestamp == _NOW

    def test_timestamp_defaults_to_utc_now(self) -> None:
        event = VoiceSessionStartedEvent(
            session_id="s",
            room_id="r",
            correlation_id="c",
            participant_identity="u",
        )
        assert event.timestamp.tzinfo is not None

    def test_is_frozen(self) -> None:
        event = VoiceSessionStartedEvent(**_BASE, participant_identity="user-42")
        with pytest.raises((TypeError, ValidationError)):
            event.session_id = "changed"  # type: ignore[misc]


class TestVoiceSessionEndedEvent:
    def test_instantiates(self) -> None:
        event = VoiceSessionEndedEvent(**_BASE, duration_secs=42.5)
        assert event.duration_secs == pytest.approx(42.5)

    def test_is_frozen(self) -> None:
        event = VoiceSessionEndedEvent(**_BASE, duration_secs=10.0)
        with pytest.raises((TypeError, ValidationError)):
            event.duration_secs = 99.9  # type: ignore[misc]


class TestVoiceTurnCompletedEvent:
    def test_instantiates_with_all_latency_fields(self) -> None:
        event = VoiceTurnCompletedEvent(
            **_BASE,
            transcript="What is the capital of France?",
            response_preview="The capital of France is Paris.",
            stt_latency_ms=120.0,
            bridge_latency_ms=300.0,
            tts_latency_ms=180.0,
            total_latency_ms=600.0,
        )
        assert event.transcript == "What is the capital of France?"
        assert event.response_preview == "The capital of France is Paris."
        assert event.stt_latency_ms == pytest.approx(120.0)
        assert event.total_latency_ms == pytest.approx(600.0)

    def test_is_frozen(self) -> None:
        event = VoiceTurnCompletedEvent(
            **_BASE,
            transcript="Hi",
            response_preview="Hello",
            stt_latency_ms=100.0,
            bridge_latency_ms=200.0,
            tts_latency_ms=150.0,
            total_latency_ms=450.0,
        )
        with pytest.raises((TypeError, ValidationError)):
            event.transcript = "changed"  # type: ignore[misc]

    def test_no_audio_bytes_field(self) -> None:
        event = VoiceTurnCompletedEvent(
            **_BASE,
            transcript="t",
            response_preview="r",
            stt_latency_ms=1.0,
            bridge_latency_ms=1.0,
            tts_latency_ms=1.0,
            total_latency_ms=3.0,
        )
        assert not hasattr(event, "audio") and not hasattr(event, "audio_bytes")


class TestVoiceTurnFailedEvent:
    def test_valid_stt_error_type(self) -> None:
        event = VoiceTurnFailedEvent(
            **_BASE, error_type="stt_error", error_message="Whisper crashed"
        )
        assert event.error_type == "stt_error"

    def test_valid_bridge_timeout_error_type(self) -> None:
        event = VoiceTurnFailedEvent(
            **_BASE, error_type="bridge_timeout", error_message="timed out"
        )
        assert event.error_type == "bridge_timeout"

    def test_valid_bridge_error_type(self) -> None:
        event = VoiceTurnFailedEvent(
            **_BASE, error_type="bridge_error", error_message="reasoner replied with error"
        )
        assert event.error_type == "bridge_error"

    def test_valid_tts_error_type(self) -> None:
        event = VoiceTurnFailedEvent(
            **_BASE, error_type="tts_error", error_message="piper failed"
        )
        assert event.error_type == "tts_error"

    def test_valid_unknown_error_type(self) -> None:
        event = VoiceTurnFailedEvent(
            **_BASE, error_type="unknown", error_message="unexpected"
        )
        assert event.error_type == "unknown"

    def test_invalid_error_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            VoiceTurnFailedEvent(
                **_BASE,
                error_type="bad_error",  # type: ignore[arg-type]
                error_message="oops",
            )

    def test_is_frozen(self) -> None:
        event = VoiceTurnFailedEvent(**_BASE, error_type="unknown", error_message="err")
        with pytest.raises((TypeError, ValidationError)):
            event.error_type = "stt_error"  # type: ignore[misc]
