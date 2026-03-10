"""Tests for POST /v1/audio/transcriptions router.

The STT dependency is overridden with a mock STTPort so no Whisper model is
loaded.  Tests use httpx via FastAPI's TestClient (synchronous wrapper).
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voice.interfaces import STTError, STTPort, TranscriptResult
from voice.stt_router import _get_stt_adapter, router

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_stt(
    text: str = "Hello world",
    language: str = "en",
    duration: float = 1.5,
) -> STTPort:
    """Return an async mock that satisfies the STTPort protocol."""
    mock = AsyncMock(spec=STTPort)
    mock.transcribe.return_value = TranscriptResult(
        text=text,
        language=language,
        duration_secs=duration,
    )
    return mock  # type: ignore[return-value]


def _build_app(stt: STTPort) -> FastAPI:
    """Build a minimal FastAPI app with the STT router and overridden dependency."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_get_stt_adapter] = lambda: stt
    return app


# ─── Success path ─────────────────────────────────────────────────────────────


class TestTranscribeSuccess:
    def test_returns_200_with_transcript(self) -> None:
        mock_stt = _make_mock_stt(text="Test transcript", language="en", duration=2.0)
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("audio.wav", io.BytesIO(b"fake-audio"), "audio/wav")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "Test transcript"
        assert body["language"] == "en"
        assert body["duration"] == pytest.approx(2.0)

    def test_calls_stt_transcribe_with_audio_bytes(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))
        audio_data = b"real-audio-bytes"

        client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.wav", io.BytesIO(audio_data), "audio/wav")},
        )

        mock_stt.transcribe.assert_awaited_once()  # type: ignore[attr-defined]
        call_args = mock_stt.transcribe.call_args  # type: ignore[attr-defined]
        assert call_args[0][0] == audio_data

    def test_accepts_ogg_content_type(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.ogg", io.BytesIO(b"ogg-data"), "audio/ogg")},
        )

        assert response.status_code == 200

    def test_accepts_mp3_content_type(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.mp3", io.BytesIO(b"mp3-data"), "audio/mpeg")},
        )

        assert response.status_code == 200


# ─── Validation errors ────────────────────────────────────────────────────────


class TestTranscribeValidation:
    def test_rejects_non_audio_mime_type_with_400(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("doc.pdf", io.BytesIO(b"pdf-data"), "application/pdf")},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error_type"] == "invalid_input"
        assert "correlation_id" in body
        assert "message" in body

    def test_rejects_text_mime_type_with_400(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("script.txt", io.BytesIO(b"text"), "text/plain")},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error_type"] == "invalid_input"

    def test_invalid_input_error_has_typed_fields(self) -> None:
        mock_stt = _make_mock_stt()
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("img.png", io.BytesIO(b"png"), "image/png")},
        )

        body = response.json()
        assert set(body.keys()) >= {"error_type", "message", "correlation_id"}
        assert body["error_type"] == "invalid_input"


# ─── Provider failure ─────────────────────────────────────────────────────────


class TestTranscribeProviderFailure:
    def test_stt_error_returns_502(self) -> None:
        mock_stt: STTPort = AsyncMock(spec=STTPort)
        mock_stt.transcribe.side_effect = STTError("whisper model failed")  # type: ignore[attr-defined]
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.wav", io.BytesIO(b"audio"), "audio/wav")},
        )

        assert response.status_code == 502
        body = response.json()
        assert body["error_type"] == "provider_unavailable"
        assert "whisper model failed" in body["message"]
        assert "correlation_id" in body

    def test_provider_unavailable_error_has_typed_fields(self) -> None:
        mock_stt: STTPort = AsyncMock(spec=STTPort)
        mock_stt.transcribe.side_effect = STTError("boom")  # type: ignore[attr-defined]
        client = TestClient(_build_app(mock_stt))

        response = client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.wav", io.BytesIO(b"audio"), "audio/wav")},
        )

        body = response.json()
        assert set(body.keys()) >= {"error_type", "message", "correlation_id"}
