"""Tests for POST /v1/audio/speech router.

The TTS dependency is overridden with a mock TTSPort so piper is never
invoked.  Tests use httpx via FastAPI's TestClient (synchronous wrapper).
"""

from __future__ import annotations

import io
import wave
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voice.interfaces import SynthesisResult, TTSError, TTSPort
from voice.providers.tts_piper import PIPER_SAMPLE_RATE
from voice.tts_router import _get_tts_adapter, router


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_wav_bytes(num_samples: int = 100) -> bytes:
    """Return a minimal valid WAV file with *num_samples* silent frames."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(PIPER_SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _make_mock_tts(
    wav_bytes: bytes | None = None,
    sample_rate: int = PIPER_SAMPLE_RATE,
    duration: float = 0.5,
) -> TTSPort:
    """Return an async mock that satisfies the TTSPort protocol."""
    if wav_bytes is None:
        wav_bytes = _make_wav_bytes()
    mock = AsyncMock(spec=TTSPort)
    mock.synthesize.return_value = SynthesisResult(
        wav_bytes=wav_bytes,
        sample_rate=sample_rate,
        duration_secs=duration,
    )
    return mock  # type: ignore[return-value]


def _build_app(tts: TTSPort) -> FastAPI:
    """Build a minimal FastAPI app with the TTS router and overridden dependency."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_get_tts_adapter] = lambda: tts
    return app


# ─── Success path ─────────────────────────────────────────────────────────────


class TestSpeechSuccess:
    def test_returns_200_with_wav_content_type(self) -> None:
        mock_tts = _make_mock_tts(duration=1.0)
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello world", "voice": "default"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

    def test_response_has_x_duration_seconds_header(self) -> None:
        mock_tts = _make_mock_tts(duration=2.5)
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Test speech", "voice": "default"},
        )

        assert "x-duration-seconds" in response.headers
        assert float(response.headers["x-duration-seconds"]) == pytest.approx(2.5)

    def test_response_has_x_sample_rate_header(self) -> None:
        mock_tts = _make_mock_tts(sample_rate=PIPER_SAMPLE_RATE)
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Test speech", "voice": "default"},
        )

        assert "x-sample-rate" in response.headers
        assert int(response.headers["x-sample-rate"]) == PIPER_SAMPLE_RATE

    def test_response_body_is_wav_bytes(self) -> None:
        wav = _make_wav_bytes(num_samples=PIPER_SAMPLE_RATE)
        mock_tts = _make_mock_tts(wav_bytes=wav)
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello", "voice": "default"},
        )

        assert response.content == wav

    def test_calls_tts_synthesize_with_input_and_voice(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Say this", "voice": "custom-voice"},
        )

        mock_tts.synthesize.assert_awaited_once()  # type: ignore[attr-defined]
        call_args = mock_tts.synthesize.call_args[0]
        assert call_args[0] == "Say this"
        assert call_args[1] == "custom-voice"

    def test_default_voice_is_used_when_not_specified(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello"},
        )

        call_args = mock_tts.synthesize.call_args[0]  # type: ignore[attr-defined]
        assert call_args[1] == "default"

    def test_input_with_only_whitespace_returns_400(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "   ", "voice": "default"},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error_type"] == "invalid_input"


# ─── Validation errors ────────────────────────────────────────────────────────


class TestSpeechValidation:
    def test_empty_input_returns_400(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "", "voice": "default"},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error_type"] == "invalid_input"

    def test_empty_input_error_has_typed_fields(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "", "voice": "default"},
        )

        body = response.json()
        assert set(body.keys()) >= {"error_type", "message", "correlation_id"}
        assert body["error_type"] == "invalid_input"
        assert "correlation_id" in body

    def test_empty_input_does_not_call_tts(self) -> None:
        mock_tts = _make_mock_tts()
        client = TestClient(_build_app(mock_tts))

        client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "", "voice": "default"},
        )

        mock_tts.synthesize.assert_not_awaited()  # type: ignore[attr-defined]


# ─── Provider failure ─────────────────────────────────────────────────────────


class TestSpeechProviderFailure:
    def test_tts_error_returns_502(self) -> None:
        mock_tts: TTSPort = AsyncMock(spec=TTSPort)
        mock_tts.synthesize.side_effect = TTSError("piper binary crashed")  # type: ignore[attr-defined]
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello", "voice": "default"},
        )

        assert response.status_code == 502
        body = response.json()
        assert body["error_type"] == "provider_unavailable"
        assert "piper binary crashed" in body["message"]
        assert "correlation_id" in body

    def test_provider_unavailable_error_has_typed_fields(self) -> None:
        mock_tts: TTSPort = AsyncMock(spec=TTSPort)
        mock_tts.synthesize.side_effect = TTSError("boom")  # type: ignore[attr-defined]
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello", "voice": "default"},
        )

        body = response.json()
        assert set(body.keys()) >= {"error_type", "message", "correlation_id"}
        assert body["error_type"] == "provider_unavailable"

    def test_provider_failure_correlation_id_is_uuid(self) -> None:
        import uuid

        mock_tts: TTSPort = AsyncMock(spec=TTSPort)
        mock_tts.synthesize.side_effect = TTSError("fail")  # type: ignore[attr-defined]
        client = TestClient(_build_app(mock_tts))

        response = client.post(
            "/v1/audio/speech",
            json={"model": "piper", "input": "Hello", "voice": "default"},
        )

        body = response.json()
        # Should not raise
        uuid.UUID(body["correlation_id"])
