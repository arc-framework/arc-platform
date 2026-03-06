"""Unit tests for PiperTTSAdapter.

The piper subprocess is patched so the actual binary is never executed.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from voice.interfaces import SynthesisResult, TTSError
from voice.providers.tts_piper import (
    PIPER_SAMPLE_RATE,
    PiperTTSAdapter,
    _calc_duration,
    _raw_to_wav,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_fake_raw_audio(num_samples: int = 22050) -> bytes:
    """Return *num_samples* frames of silent 16-bit PCM."""
    return b"\x00\x00" * num_samples


def _make_completed_process(stdout: bytes = b"", returncode: int = 0) -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


# ─── _raw_to_wav ──────────────────────────────────────────────────────────────


class TestRawToWav:
    def test_produces_valid_wav_header(self) -> None:
        raw = _make_fake_raw_audio(100)
        wav = _raw_to_wav(raw, PIPER_SAMPLE_RATE)
        # RIFF header magic bytes
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"

    def test_wav_contains_raw_audio(self) -> None:
        raw = _make_fake_raw_audio(10)
        wav = _raw_to_wav(raw, PIPER_SAMPLE_RATE)
        # The raw bytes should appear inside the WAV container
        assert raw in wav

    def test_empty_raw_audio_produces_wav(self) -> None:
        wav = _raw_to_wav(b"", PIPER_SAMPLE_RATE)
        assert wav[:4] == b"RIFF"


# ─── _calc_duration ───────────────────────────────────────────────────────────


class TestCalcDuration:
    def test_one_second_of_audio(self) -> None:
        # 22050 samples * 2 bytes/sample = 44100 data bytes + 44 header = 44144
        raw = _make_fake_raw_audio(PIPER_SAMPLE_RATE)
        wav = _raw_to_wav(raw, PIPER_SAMPLE_RATE)
        duration = _calc_duration(wav)
        assert abs(duration - 1.0) < 0.01

    def test_zero_data_returns_zero(self) -> None:
        wav = _raw_to_wav(b"", PIPER_SAMPLE_RATE)
        duration = _calc_duration(wav)
        assert duration == pytest.approx(0.0, abs=0.001)


# ─── PiperTTSAdapter construction ────────────────────────────────────────────


class TestPiperTTSAdapterConstruction:
    def test_default_binary_path(self) -> None:
        adapter = PiperTTSAdapter()
        assert adapter._piper_bin == "/usr/local/bin/piper"

    def test_custom_binary_path(self) -> None:
        adapter = PiperTTSAdapter(piper_bin="/opt/piper/piper")
        assert adapter._piper_bin == "/opt/piper/piper"


# ─── _run_piper (sync helper) ─────────────────────────────────────────────────


class TestRunPiper:
    def test_calls_subprocess_run_with_correct_args(self) -> None:
        raw_audio = _make_fake_raw_audio(100)
        adapter = PiperTTSAdapter(piper_bin="/usr/bin/piper")

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)) as mock_run:
            result = adapter._run_piper("Hello world", "en_US-lessac-medium")

        mock_run.assert_called_once_with(
            ["/usr/bin/piper", "--model", "en_US-lessac-medium", "--output-raw"],
            input=b"Hello world",
            capture_output=True,
            check=True,
        )
        assert result == raw_audio

    def test_raises_tts_error_on_called_process_error(self) -> None:
        adapter = PiperTTSAdapter()
        exc = subprocess.CalledProcessError(1, "piper", stderr=b"model not found")

        with patch("subprocess.run", side_effect=exc):
            with pytest.raises(TTSError, match="piper exited with code 1"):
                adapter._run_piper("Hello", "bad-voice")

    def test_raises_tts_error_when_binary_not_found(self) -> None:
        adapter = PiperTTSAdapter(piper_bin="/nonexistent/piper")

        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(TTSError, match="piper binary not found"):
                adapter._run_piper("Hello", "some-voice")

    def test_raises_tts_error_on_generic_exception(self) -> None:
        adapter = PiperTTSAdapter()

        with patch("subprocess.run", side_effect=OSError("permission denied")):
            with pytest.raises(TTSError, match="permission denied"):
                adapter._run_piper("Hello", "voice")


# ─── PiperTTSAdapter.synthesize (async) ──────────────────────────────────────


class TestPiperTTSAdapterSynthesize:
    async def test_synthesize_returns_synthesis_result(self) -> None:
        raw_audio = _make_fake_raw_audio(PIPER_SAMPLE_RATE)
        adapter = PiperTTSAdapter()

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)):
            result = await adapter.synthesize("Hello world", "en_US-lessac-medium")

        assert isinstance(result, SynthesisResult)
        assert result.sample_rate == PIPER_SAMPLE_RATE
        # WAV header magic
        assert result.wav_bytes[:4] == b"RIFF"

    async def test_synthesize_duration_approximately_correct(self) -> None:
        # 1 second of audio at 22050 Hz
        raw_audio = _make_fake_raw_audio(PIPER_SAMPLE_RATE)
        adapter = PiperTTSAdapter()

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)):
            result = await adapter.synthesize("test", "voice")

        assert abs(result.duration_secs - 1.0) < 0.05

    async def test_synthesize_raises_tts_error_on_subprocess_failure(self) -> None:
        adapter = PiperTTSAdapter()
        exc = subprocess.CalledProcessError(1, "piper", stderr=b"error")

        with patch("subprocess.run", side_effect=exc):
            with pytest.raises(TTSError):
                await adapter.synthesize("Hello", "voice")

    async def test_synthesize_passes_voice_to_piper(self) -> None:
        raw_audio = _make_fake_raw_audio(100)
        adapter = PiperTTSAdapter(piper_bin="/piper")

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)) as mock_run:
            await adapter.synthesize("Say this", "custom-voice-model")

        call_args = mock_run.call_args[0][0]
        assert "--model" in call_args
        model_idx = call_args.index("--model")
        assert call_args[model_idx + 1] == "custom-voice-model"

    async def test_synthesize_encodes_text_as_utf8(self) -> None:
        raw_audio = _make_fake_raw_audio(100)
        adapter = PiperTTSAdapter()

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)) as mock_run:
            await adapter.synthesize("Héllo wörld", "voice")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["input"] == "Héllo wörld".encode("utf-8")

    async def test_synthesize_empty_text_produces_result(self) -> None:
        # Empty text is allowed at the adapter level; validation happens in router
        raw_audio = b""
        adapter = PiperTTSAdapter()

        with patch("subprocess.run", return_value=_make_completed_process(raw_audio)):
            result = await adapter.synthesize("", "voice")

        assert isinstance(result, SynthesisResult)
        assert result.duration_secs == pytest.approx(0.0, abs=0.001)
