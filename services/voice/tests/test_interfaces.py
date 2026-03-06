"""Tests for voice/interfaces.py — Ports, result dataclasses, and custom exceptions."""

from __future__ import annotations

import pytest

from voice.interfaces import (
    BridgeError,
    LLMBridgePort,
    STTError,
    STTPort,
    SynthesisResult,
    TTSError,
    TTSPort,
    TranscriptResult,
)


# ─── Result Dataclasses ────────────────────────────────────────────────────────


def test_transcript_result_fields() -> None:
    r = TranscriptResult(text="hello", language="en", duration_secs=1.23)
    assert r.text == "hello"
    assert r.language == "en"
    assert r.duration_secs == 1.23


def test_synthesis_result_fields() -> None:
    r = SynthesisResult(wav_bytes=b"\x00\x01", sample_rate=22050, duration_secs=0.5)
    assert r.wav_bytes == b"\x00\x01"
    assert r.sample_rate == 22050
    assert r.duration_secs == 0.5


# ─── Custom Exceptions ─────────────────────────────────────────────────────────


def test_stt_error_is_exception() -> None:
    assert issubclass(STTError, Exception)
    err = STTError("transcription failed")
    assert str(err) == "transcription failed"


def test_tts_error_is_exception() -> None:
    assert issubclass(TTSError, Exception)
    err = TTSError("synthesis failed")
    assert str(err) == "synthesis failed"


def test_bridge_error_explicit_override() -> None:
    # error_type override must win over the is_timeout derivation
    err = BridgeError("upstream error", is_timeout=True, error_type="custom_override")
    assert err.is_timeout is True
    assert err.error_type == "custom_override"
    assert isinstance(err, Exception)


def test_bridge_error_default_error_type_timeout() -> None:
    err = BridgeError("timed out", is_timeout=True)
    assert err.error_type == "bridge_timeout"


def test_bridge_error_default_error_type_non_timeout() -> None:
    err = BridgeError("reasoner error", is_timeout=False)
    assert err.error_type == "bridge_error"


# ─── Protocol Structural Conformance ──────────────────────────────────────────


class MockSTT:
    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptResult:
        return TranscriptResult(text="ok", language="en", duration_secs=0.1)


class MockTTS:
    async def synthesize(self, text: str, voice: str) -> SynthesisResult:
        return SynthesisResult(wav_bytes=b"", sample_rate=22050, duration_secs=0.0)


class MockBridge:
    async def reason(
        self, transcript: str, session_id: str, correlation_id: str
    ) -> str:
        return "response"


def test_stt_port_protocol_satisfied() -> None:
    adapter = MockSTT()
    assert isinstance(adapter, STTPort)


def test_tts_port_protocol_satisfied() -> None:
    adapter = MockTTS()
    assert isinstance(adapter, TTSPort)


def test_llm_bridge_port_protocol_satisfied() -> None:
    bridge = MockBridge()
    assert isinstance(bridge, LLMBridgePort)


# ─── Protocol method signatures callable ──────────────────────────────────────


async def test_mock_stt_transcribe() -> None:
    adapter = MockSTT()
    result = await adapter.transcribe(b"audio", language="en")
    assert isinstance(result, TranscriptResult)


async def test_mock_tts_synthesize() -> None:
    adapter = MockTTS()
    result = await adapter.synthesize("hello", voice="default")
    assert isinstance(result, SynthesisResult)


async def test_mock_bridge_reason() -> None:
    bridge = MockBridge()
    text = await bridge.reason("hello", session_id="s1", correlation_id="c1")
    assert isinstance(text, str)
