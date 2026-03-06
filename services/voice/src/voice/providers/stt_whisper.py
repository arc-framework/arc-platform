"""faster-whisper STT adapter implementing STTPort."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import faster_whisper

from voice.interfaces import STTError, STTPort, TranscriptResult

# WhisperModel is accessed via the module reference so tests can patch
# faster_whisper.WhisperModel without needing a module-level name here.
WhisperModel = faster_whisper.WhisperModel


class WhisperSTTAdapter:
    """STT adapter backed by faster-whisper, implementing STTPort.

    Model loading is deferred to the first call to ``transcribe()`` or an
    explicit call to ``load()``.  This keeps import time fast and allows the
    adapter to be constructed before the event loop starts.
    """

    def __init__(self, model: str = "tiny", device: str = "cpu") -> None:
        self._model_name = model
        self._device = device
        self._model: Any | None = None

    def load(self) -> None:
        """Eagerly load the WhisperModel.  Safe to call multiple times."""
        if self._model is None:
            self._model = WhisperModel(self._model_name, device=self._device)

    def _ensure_loaded(self) -> Any:
        if self._model is None:
            self.load()
        return self._model

    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptResult:
        """Transcribe *audio_bytes* and return a TranscriptResult.

        Runs the CPU-bound faster-whisper call in the default thread-pool
        executor so the event loop is not blocked.

        Raises:
            STTError: on any exception from the underlying WhisperModel.
        """
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, self._run_transcribe, audio_bytes, language
            )
        except STTError:
            raise
        except Exception as exc:
            raise STTError(str(exc)) from exc
        return result

    def _run_transcribe(
        self, audio_bytes: bytes, language: str | None
    ) -> TranscriptResult:
        """Synchronous transcription — runs in a thread-pool executor."""
        import io

        model = self._ensure_loaded()
        kwargs: dict[str, object] = {}
        if language:
            kwargs["language"] = language

        t0 = time.perf_counter()
        try:
            segments, info = model.transcribe(io.BytesIO(audio_bytes), **kwargs)
            text = "".join(segment.text for segment in segments)
        except Exception as exc:
            raise STTError(str(exc)) from exc
        duration = time.perf_counter() - t0

        detected_lang: str = info.language if info.language else (language or "")
        return TranscriptResult(
            text=text.strip(),
            language=detected_lang,
            duration_secs=duration,
        )


# Verify the class satisfies the STTPort protocol at import time.
assert isinstance(WhisperSTTAdapter(), STTPort)  # noqa: S101
