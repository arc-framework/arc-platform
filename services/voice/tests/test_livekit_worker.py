"""Tests for the LiveKit voice agent worker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from voice.config import Settings
from voice.interfaces import BridgeError, STTError, SynthesisResult, TranscriptResult, TTSError
from voice.livekit_worker import VoiceAgentWorker, _compute_rms

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    return Settings(
        livekit_url="ws://localhost:7880",
        livekit_api_key="test-key",
        livekit_api_secret="test-secret",
        livekit_room_name="arc-voice",
        vad_threshold=500.0,
        vad_silence_frames=20,
    )


@pytest.fixture
def mock_stt() -> AsyncMock:
    stt = AsyncMock()
    stt.transcribe = AsyncMock(
        return_value=TranscriptResult(
            text="Hello world",
            language="en",
            duration_secs=1.5,
        )
    )
    return stt


@pytest.fixture
def mock_tts() -> AsyncMock:
    tts = AsyncMock()
    tts.synthesize = AsyncMock(
        return_value=SynthesisResult(
            wav_bytes=b"RIFF" + b"\x00" * 40,
            sample_rate=16000,
            duration_secs=0.5,
        )
    )
    return tts


@pytest.fixture
def mock_bridge() -> AsyncMock:
    bridge = AsyncMock()
    bridge.reason = AsyncMock(return_value="The answer is 42.")
    return bridge


@pytest.fixture
def mock_publisher() -> MagicMock:
    pub = MagicMock()
    pub.publish_session_started = MagicMock()
    pub.publish_session_ended = MagicMock()
    pub.publish_turn_completed = MagicMock()
    pub.publish_turn_failed = MagicMock()
    return pub


@pytest.fixture
def worker(
    mock_stt: AsyncMock,
    mock_tts: AsyncMock,
    mock_bridge: AsyncMock,
    mock_publisher: MagicMock,
    settings: Settings,
) -> VoiceAgentWorker:
    return VoiceAgentWorker(
        stt=mock_stt,
        tts=mock_tts,
        bridge=mock_bridge,
        publisher=mock_publisher,
        settings=settings,
    )


# ─── _compute_rms unit tests ──────────────────────────────────────────────────


def test_compute_rms_silent_chunk_returns_zero() -> None:
    """Silent chunk (all zeros) should return RMS ≈ 0."""
    samples = np.zeros(160, dtype=np.int16)
    chunk = samples.tobytes()
    rms = _compute_rms(chunk)
    assert rms == pytest.approx(0.0)


def test_compute_rms_empty_chunk_returns_zero() -> None:
    """Empty bytes should return 0.0 without error."""
    rms = _compute_rms(b"")
    assert rms == pytest.approx(0.0)


def test_compute_rms_speech_chunk_returns_positive() -> None:
    """Non-zero samples should produce a positive RMS."""
    # Constant 1000 amplitude sine-wave-like signal
    samples = np.full(160, 1000, dtype=np.int16)
    chunk = samples.tobytes()
    rms = _compute_rms(chunk)
    assert rms > 0.0
    assert rms == pytest.approx(1000.0)


def test_compute_rms_known_value() -> None:
    """RMS of [3, 4] int16 = sqrt((9+16)/2) = sqrt(12.5) ≈ 3.535."""
    samples = np.array([3, 4], dtype=np.int16)
    chunk = samples.tobytes()
    rms = _compute_rms(chunk)
    import math
    assert rms == pytest.approx(math.sqrt(12.5), rel=1e-5)


# ─── _handle_turn — success path ──────────────────────────────────────────────


async def test_handle_turn_success_publishes_completed_event(
    worker: VoiceAgentWorker,
    mock_stt: AsyncMock,
    mock_bridge: AsyncMock,
    mock_tts: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """Happy path: STT → bridge → TTS all succeed, publishes VoiceTurnCompletedEvent."""
    audio = b"\x00" * 3200  # 100ms of 16kHz 16-bit mono

    await worker._handle_turn(
        session_id="session-1",
        audio_bytes=audio,
        room_name="arc-voice",
    )

    mock_stt.transcribe.assert_awaited_once_with(audio, language=None)
    mock_bridge.reason.assert_awaited_once_with(
        "Hello world", "session-1", mock_bridge.reason.call_args.args[2]
    )
    mock_tts.synthesize.assert_awaited_once()
    mock_publisher.publish_turn_completed.assert_called_once()
    mock_publisher.publish_turn_failed.assert_not_called()


async def test_handle_turn_success_records_turn_histogram(
    worker: VoiceAgentWorker,
) -> None:
    """Turn histogram should be recorded on success."""
    audio = b"\x00" * 3200

    with patch("voice.livekit_worker.turn_latency") as mock_hist:
        mock_hist.record = MagicMock()
        await worker._handle_turn(
            session_id="session-1",
            audio_bytes=audio,
            room_name="arc-voice",
        )
        mock_hist.record.assert_called_once()
        elapsed = mock_hist.record.call_args.args[0]
        assert elapsed >= 0.0


# ─── _handle_turn — error paths ───────────────────────────────────────────────


async def test_handle_turn_stt_error_publishes_failed_event(
    worker: VoiceAgentWorker,
    mock_stt: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """STTError → VoiceTurnFailedEvent with error_type='stt_error'."""
    mock_stt.transcribe.side_effect = STTError("Whisper failed")

    await worker._handle_turn(
        session_id="session-2",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.error_type == "stt_error"
    mock_publisher.publish_turn_completed.assert_not_called()


async def test_handle_turn_bridge_timeout_publishes_failed_event(
    worker: VoiceAgentWorker,
    mock_bridge: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """BridgeError(is_timeout=True) → VoiceTurnFailedEvent with error_type='bridge_timeout'."""
    mock_bridge.reason.side_effect = BridgeError("timeout", is_timeout=True)

    await worker._handle_turn(
        session_id="session-3",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.error_type == "bridge_timeout"
    mock_publisher.publish_turn_completed.assert_not_called()


async def test_handle_turn_bridge_error_publishes_failed_event(
    worker: VoiceAgentWorker,
    mock_bridge: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """BridgeError(is_timeout=False) → VoiceTurnFailedEvent with error_type='bridge_error'."""
    mock_bridge.reason.side_effect = BridgeError("reasoner error", is_timeout=False)

    await worker._handle_turn(
        session_id="session-4",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.error_type == "bridge_error"
    mock_publisher.publish_turn_completed.assert_not_called()


async def test_handle_turn_tts_error_publishes_failed_event(
    worker: VoiceAgentWorker,
    mock_tts: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """TTSError → VoiceTurnFailedEvent with error_type='tts_error'."""
    mock_tts.synthesize.side_effect = TTSError("Piper crashed")

    await worker._handle_turn(
        session_id="session-5",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.error_type == "tts_error"
    mock_publisher.publish_turn_completed.assert_not_called()


async def test_handle_turn_unknown_error_publishes_failed_event(
    worker: VoiceAgentWorker,
    mock_stt: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """Unexpected Exception → VoiceTurnFailedEvent with error_type='unknown'."""
    mock_stt.transcribe.side_effect = RuntimeError("something unexpected")

    await worker._handle_turn(
        session_id="session-6",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.error_type == "unknown"
    mock_publisher.publish_turn_completed.assert_not_called()


async def test_handle_turn_never_raises(
    worker: VoiceAgentWorker,
    mock_stt: AsyncMock,
) -> None:
    """Exceptions in _handle_turn must never propagate — worker should stay alive."""
    mock_stt.transcribe.side_effect = Exception("catastrophic failure")

    # Should not raise
    await worker._handle_turn(
        session_id="session-7",
        audio_bytes=b"\x00" * 3200,
        room_name="arc-voice",
    )


# ─── _handle_turn — event field correctness ───────────────────────────────────


async def test_handle_turn_completed_event_fields(
    worker: VoiceAgentWorker,
    mock_publisher: MagicMock,
) -> None:
    """VoiceTurnCompletedEvent fields are correctly populated."""
    await worker._handle_turn(
        session_id="sess-fields",
        audio_bytes=b"\x00" * 3200,
        room_name="room-a",
    )

    mock_publisher.publish_turn_completed.assert_called_once()
    event = mock_publisher.publish_turn_completed.call_args.args[0]
    assert event.session_id == "sess-fields"
    assert event.transcript == "Hello world"
    assert "42" in event.response_preview
    assert event.stt_latency_ms >= 0.0
    assert event.bridge_latency_ms >= 0.0
    assert event.tts_latency_ms >= 0.0
    assert event.total_latency_ms >= 0.0


async def test_handle_turn_failed_event_fields(
    worker: VoiceAgentWorker,
    mock_stt: AsyncMock,
    mock_publisher: MagicMock,
) -> None:
    """VoiceTurnFailedEvent fields are correctly populated."""
    mock_stt.transcribe.side_effect = STTError("bad audio")

    await worker._handle_turn(
        session_id="sess-fail",
        audio_bytes=b"\x00" * 3200,
        room_name="room-b",
    )

    mock_publisher.publish_turn_failed.assert_called_once()
    event = mock_publisher.publish_turn_failed.call_args.args[0]
    assert event.session_id == "sess-fail"
    assert event.error_type == "stt_error"
    assert "bad audio" in event.error_message
    assert event.correlation_id  # non-empty UUID


# ─── VAD state machine ────────────────────────────────────────────────────────


async def test_vad_fires_turn_after_silence_threshold(
    worker: VoiceAgentWorker,
) -> None:
    """VAD state machine fires _handle_turn when silence_frames > vad_silence_frames."""
    # Patch _handle_turn to track calls
    turns_fired: list[bytes] = []

    async def fake_handle_turn(session_id: str, audio_bytes: bytes, room_name: str) -> None:
        turns_fired.append(audio_bytes)

    worker._handle_turn = fake_handle_turn  # type: ignore[method-assign]

    # Simulate: 5 speech frames followed by vad_silence_frames+1 silence frames
    speech_sample = np.full(160, 1000, dtype=np.int16).tobytes()  # RMS=1000 > threshold
    silence_sample = np.zeros(160, dtype=np.int16).tobytes()  # RMS=0 < threshold

    # Feed speech frames
    for _ in range(5):
        await worker._process_audio_chunk(speech_sample, "sess-vad", "room-vad")

    # Feed silence frames to exceed the threshold
    for _ in range(worker._settings.vad_silence_frames + 1):
        await worker._process_audio_chunk(silence_sample, "sess-vad", "room-vad")

    assert len(turns_fired) == 1
    # The accumulated audio should contain our speech frames
    assert len(turns_fired[0]) == 5 * len(speech_sample)


async def test_vad_no_turn_without_speech(
    worker: VoiceAgentWorker,
) -> None:
    """VAD should not fire a turn if no speech was detected."""
    turns_fired: list[bytes] = []

    async def fake_handle_turn(session_id: str, audio_bytes: bytes, room_name: str) -> None:
        turns_fired.append(audio_bytes)

    worker._handle_turn = fake_handle_turn  # type: ignore[method-assign]

    silence_sample = np.zeros(160, dtype=np.int16).tobytes()
    for _ in range(50):
        await worker._process_audio_chunk(silence_sample, "sess-vad", "room-vad")

    assert len(turns_fired) == 0


async def test_vad_silence_below_threshold_does_not_trigger(
    worker: VoiceAgentWorker,
) -> None:
    """VAD should not trigger until silence_frames exceeds the threshold."""
    turns_fired: list[bytes] = []

    async def fake_handle_turn(session_id: str, audio_bytes: bytes, room_name: str) -> None:
        turns_fired.append(audio_bytes)

    worker._handle_turn = fake_handle_turn  # type: ignore[method-assign]

    speech_sample = np.full(160, 1000, dtype=np.int16).tobytes()
    silence_sample = np.zeros(160, dtype=np.int16).tobytes()

    # Feed speech, then silence but NOT enough frames
    for _ in range(3):
        await worker._process_audio_chunk(speech_sample, "sess-vad2", "room-vad")

    for _ in range(worker._settings.vad_silence_frames - 1):
        await worker._process_audio_chunk(silence_sample, "sess-vad2", "room-vad")

    assert len(turns_fired) == 0


# ─── stop() ───────────────────────────────────────────────────────────────────


async def test_stop_sets_stop_flag(worker: VoiceAgentWorker) -> None:
    """stop() should set the internal stop flag."""
    assert not worker._stopped
    await worker.stop()
    assert worker._stopped


async def test_run_exits_when_stopped(
    mock_stt: AsyncMock,
    mock_tts: AsyncMock,
    mock_bridge: AsyncMock,
    mock_publisher: MagicMock,
    settings: Settings,
) -> None:
    """run() should exit cleanly when stop() is called."""
    worker = VoiceAgentWorker(
        stt=mock_stt,
        tts=mock_tts,
        bridge=mock_bridge,
        publisher=mock_publisher,
        settings=settings,
    )

    # Mock the livekit.rtc.Room so run() doesn't make real network calls
    mock_room = MagicMock()
    mock_room.connect = AsyncMock()
    mock_room.disconnect = AsyncMock()
    mock_room.on = MagicMock()

    with patch("voice.livekit_worker.rtc") as mock_rtc:
        mock_rtc.Room.return_value = mock_room
        # Signal stop before run() begins its loop
        await worker.stop()
        # run() should return immediately after calling stop()
        await worker.run()

    mock_room.disconnect.assert_awaited_once()
