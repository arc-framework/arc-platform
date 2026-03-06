"""Piper TTS adapter implementing TTSPort.

Piper runs as a subprocess: it reads text from stdin and writes raw 16-bit
PCM audio to stdout.  The raw audio is wrapped in a WAV container before
being returned to the caller.
"""

from __future__ import annotations

import asyncio
import io
import subprocess
import wave

from voice.interfaces import SynthesisResult, TTSError, TTSPort

# Piper outputs 16-bit mono PCM at 22050 Hz by default.
PIPER_SAMPLE_RATE: int = 22050
_BYTES_PER_SAMPLE: int = 2  # 16-bit = 2 bytes


def _raw_to_wav(raw_audio: bytes, sample_rate: int) -> bytes:
    """Wrap raw 16-bit mono PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(_BYTES_PER_SAMPLE)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_audio)
    return buf.getvalue()


def _calc_duration(wav_bytes: bytes, sample_rate: int) -> float:
    """Estimate audio duration from WAV byte length.

    Uses the data section size rather than the full WAV payload so the WAV
    header overhead is excluded from the calculation.
    """
    # WAV header is 44 bytes for a standard PCM file.
    data_bytes = max(0, len(wav_bytes) - 44)
    return data_bytes / (sample_rate * _BYTES_PER_SAMPLE)


class PiperTTSAdapter:
    """TTS adapter backed by the piper binary, implementing TTSPort.

    The subprocess is executed in the default thread-pool executor so the
    event loop is never blocked by the I/O-bound piper process.
    """

    def __init__(self, piper_bin: str = "/usr/local/bin/piper") -> None:
        self._piper_bin = piper_bin

    def _run_piper(self, text: str, voice: str) -> bytes:
        """Synchronous piper invocation — runs inside a thread-pool executor.

        Returns raw 16-bit PCM bytes on success.

        Raises:
            TTSError: when piper exits with a non-zero code or cannot be found.
        """
        try:
            result = subprocess.run(
                [self._piper_bin, "--model", voice, "--output-raw"],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr_msg = exc.stderr.decode("utf-8", errors="replace").strip()
            raise TTSError(
                f"piper exited with code {exc.returncode}: {stderr_msg}"
            ) from exc
        except FileNotFoundError as exc:
            raise TTSError(
                f"piper binary not found at {self._piper_bin!r}"
            ) from exc
        except Exception as exc:
            raise TTSError(str(exc)) from exc

        return result.stdout

    async def synthesize(self, text: str, voice: str) -> SynthesisResult:
        """Synthesize *text* using piper and return a SynthesisResult.

        The subprocess is run in the default thread-pool executor so the
        event loop is not blocked.

        Raises:
            TTSError: on any piper subprocess failure.
        """
        loop = asyncio.get_running_loop()
        try:
            raw_audio: bytes = await loop.run_in_executor(
                None, self._run_piper, text, voice
            )
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(str(exc)) from exc

        wav_bytes = _raw_to_wav(raw_audio, PIPER_SAMPLE_RATE)
        duration_secs = _calc_duration(wav_bytes, PIPER_SAMPLE_RATE)

        return SynthesisResult(
            wav_bytes=wav_bytes,
            sample_rate=PIPER_SAMPLE_RATE,
            duration_secs=duration_secs,
        )


# Verify the class satisfies the TTSPort protocol at import time.
assert isinstance(PiperTTSAdapter(), TTSPort)  # noqa: S101
