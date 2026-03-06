"""Unit tests for WhisperSTTAdapter.

WhisperModel is patched so no actual model is downloaded or run.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from voice.interfaces import STTError, TranscriptResult
from voice.providers.stt_whisper import WhisperSTTAdapter


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_model_mock(
    segments: list[str] | None = None,
    language: str = "en",
) -> MagicMock:
    """Return a mock WhisperModel whose transcribe() yields fake segments."""
    if segments is None:
        segments = ["Hello, world."]

    mock_model = MagicMock()
    mock_segments = [SimpleNamespace(text=s) for s in segments]
    mock_info = SimpleNamespace(language=language)
    mock_model.transcribe.return_value = (iter(mock_segments), mock_info)
    return mock_model


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestWhisperSTTAdapterConstruction:
    def test_does_not_load_model_at_construction(self) -> None:
        with patch("faster_whisper.WhisperModel") as mock_cls:
            _adapter = WhisperSTTAdapter(model="tiny", device="cpu")
            mock_cls.assert_not_called()

    def test_default_params(self) -> None:
        adapter = WhisperSTTAdapter()
        assert adapter._model_name == "tiny"
        assert adapter._device == "cpu"

    def test_custom_params(self) -> None:
        adapter = WhisperSTTAdapter(model="base", device="cuda")
        assert adapter._model_name == "base"
        assert adapter._device == "cuda"


class TestWhisperSTTAdapterLoad:
    def test_load_creates_whisper_model(self) -> None:
        adapter = WhisperSTTAdapter(model="tiny", device="cpu")
        # Patch the module-level alias that the adapter's load() uses
        with patch("voice.providers.stt_whisper.WhisperModel", create=True) as mock_cls:
            mock_cls.return_value = _make_model_mock()
            adapter.load()
            mock_cls.assert_called_once_with("tiny", device="cpu")

    def test_load_idempotent(self) -> None:
        adapter = WhisperSTTAdapter()
        mock_instance = _make_model_mock()
        with patch("voice.providers.stt_whisper.WhisperModel", create=True) as mock_cls:
            mock_cls.return_value = mock_instance
            adapter.load()
            adapter.load()
            # WhisperModel constructor called only once
            mock_cls.assert_called_once()


class TestWhisperSTTAdapterTranscribe:
    async def test_transcribe_returns_transcript_result(self) -> None:
        adapter = WhisperSTTAdapter()
        mock_model = _make_model_mock(segments=["Hello, world."], language="en")
        adapter._model = mock_model  # inject pre-loaded mock

        result = await adapter.transcribe(b"fake-audio-data")

        assert isinstance(result, TranscriptResult)
        assert result.text == "Hello, world."
        assert result.language == "en"
        assert result.duration_secs >= 0.0

    async def test_transcribe_joins_multiple_segments(self) -> None:
        adapter = WhisperSTTAdapter()
        adapter._model = _make_model_mock(
            segments=["First segment.", " Second segment."], language="fr"
        )

        result = await adapter.transcribe(b"audio")

        assert result.text == "First segment. Second segment."
        assert result.language == "fr"

    async def test_transcribe_passes_language_hint(self) -> None:
        adapter = WhisperSTTAdapter()
        mock_model = _make_model_mock()
        adapter._model = mock_model

        await adapter.transcribe(b"audio", language="de")

        _call_kwargs = mock_model.transcribe.call_args[1]
        assert _call_kwargs.get("language") == "de"

    async def test_transcribe_no_language_hint_omits_kwarg(self) -> None:
        adapter = WhisperSTTAdapter()
        mock_model = _make_model_mock()
        adapter._model = mock_model

        await adapter.transcribe(b"audio", language=None)

        _call_kwargs = mock_model.transcribe.call_args[1]
        assert "language" not in _call_kwargs

    async def test_transcribe_raises_stt_error_on_model_exception(self) -> None:
        adapter = WhisperSTTAdapter()
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("model exploded")
        adapter._model = mock_model

        with pytest.raises(STTError, match="model exploded"):
            await adapter.transcribe(b"audio")

    async def test_transcribe_lazy_loads_model(self) -> None:
        adapter = WhisperSTTAdapter(model="small", device="cpu")
        mock_instance = _make_model_mock()

        with patch("voice.providers.stt_whisper.WhisperModel", create=True) as mock_cls:
            mock_cls.return_value = mock_instance
            result = await adapter.transcribe(b"audio")

        mock_cls.assert_called_once_with("small", device="cpu")
        assert isinstance(result, TranscriptResult)

    async def test_transcribe_strips_whitespace_from_text(self) -> None:
        adapter = WhisperSTTAdapter()
        adapter._model = _make_model_mock(segments=["  padded text  "], language="en")

        result = await adapter.transcribe(b"audio")

        assert result.text == "padded text"
