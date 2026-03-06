"""Load / latency benchmark for the voice pipeline.

Verifies p95 turn latency ≤ 1550ms under mocked concurrent turns.
No real external services required — all adapters are async mocks that
simulate realistic I/O delays via asyncio.sleep().
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np

from voice.config import Settings
from voice.interfaces import SynthesisResult, TranscriptResult
from voice.livekit_worker import VoiceAgentWorker, _compute_rms

# ─── Factory helper ───────────────────────────────────────────────────────────


async def _make_worker(
    stt_delay: float = 0.05,
    tts_delay: float = 0.05,
    bridge_delay: float = 0.1,
) -> VoiceAgentWorker:
    """Build a VoiceAgentWorker with mocked adapters simulating realistic latency."""
    settings = Settings()

    stt = AsyncMock()

    async def stt_transcribe(audio_bytes: bytes, language: str | None = None) -> TranscriptResult:
        await asyncio.sleep(stt_delay)
        return TranscriptResult(text="hello", language="en", duration_secs=0.1)

    stt.transcribe = stt_transcribe

    tts = AsyncMock()

    async def tts_synthesize(text: str, voice: str) -> SynthesisResult:
        await asyncio.sleep(tts_delay)
        # Minimal valid-looking bytes (real WAV header not required — _publish_audio
        # handles parse errors gracefully and never propagates them)
        return SynthesisResult(
            wav_bytes=b"RIFF" + b"\x00" * 40, sample_rate=22050, duration_secs=0.5
        )

    tts.synthesize = tts_synthesize

    bridge = AsyncMock()

    async def bridge_reason(transcript: str, session_id: str, correlation_id: str) -> str:
        await asyncio.sleep(bridge_delay)
        return "I heard you say: " + transcript

    bridge.reason = bridge_reason

    publisher = MagicMock()
    publisher.publish_turn_completed = MagicMock()
    publisher.publish_turn_failed = MagicMock()

    return VoiceAgentWorker(stt=stt, tts=tts, bridge=bridge, publisher=publisher, settings=settings)


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of data (0–100)."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100.0
    lo = int(k)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[lo]
    frac = k - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


# ─── Single turn latency ──────────────────────────────────────────────────────


async def test_single_turn_latency_under_1000ms() -> None:
    """One turn with 50+100+50ms simulated delays must finish well under 1000ms.

    The combined mock delay is ~200ms; anything > 800ms of overhead would be
    a red flag indicating a regression in the pipeline hot path.
    """
    worker = await _make_worker(stt_delay=0.05, bridge_delay=0.1, tts_delay=0.05)
    audio = b"\x00" * 3200  # 100ms of 16 kHz 16-bit mono silence

    start = time.monotonic()
    await worker._handle_turn(session_id="latency-single", audio_bytes=audio, room_name="arc-voice")
    elapsed_ms = (time.monotonic() - start) * 1000.0

    assert elapsed_ms < 1000.0, f"Single turn took {elapsed_ms:.1f}ms — expected < 1000ms"


# ─── Sequential p95 ──────────────────────────────────────────────────────────


async def test_p95_latency_10_turns_sequential() -> None:
    """10 sequential turns at ~200ms each must yield p95 ≤ 1550ms.

    Sequential execution means each turn is independent; no concurrency
    pressure.  With 200ms of mock I/O the p95 should comfortably land
    around 200–300ms.
    """
    worker = await _make_worker(stt_delay=0.05, bridge_delay=0.1, tts_delay=0.05)
    audio = b"\x00" * 3200
    latencies_ms: list[float] = []

    for i in range(10):
        start = time.monotonic()
        await worker._handle_turn(
            session_id=f"seq-{i}", audio_bytes=audio, room_name="arc-voice"
        )
        latencies_ms.append((time.monotonic() - start) * 1000.0)

    p95 = _percentile(latencies_ms, 95)
    assert p95 <= 1550.0, f"Sequential p95 = {p95:.1f}ms — expected ≤ 1550ms"


# ─── Concurrent p95 ──────────────────────────────────────────────────────────


async def test_p95_latency_5_concurrent_turns() -> None:
    """5 concurrent turns at ~200ms each must yield p95 ≤ 1550ms.

    asyncio.gather() runs all turns concurrently so total wall-clock time
    is close to a single turn duration.  p95 across the 5 concurrent turn
    durations should be well under the 1550ms ceiling.
    """
    worker = await _make_worker(stt_delay=0.05, bridge_delay=0.1, tts_delay=0.05)
    audio = b"\x00" * 3200

    async def _timed_turn(session_id: str) -> float:
        start = time.monotonic()
        await worker._handle_turn(
            session_id=session_id, audio_bytes=audio, room_name="arc-voice"
        )
        return (time.monotonic() - start) * 1000.0

    latencies_ms: list[float] = await asyncio.gather(
        *[_timed_turn(f"concurrent-{i}") for i in range(5)]
    )

    p95 = _percentile(list(latencies_ms), 95)
    assert p95 <= 1550.0, f"Concurrent p95 = {p95:.1f}ms — expected ≤ 1550ms"


# ─── _compute_rms — latency-adjacent unit tests ───────────────────────────────


def test_compute_rms_silent_chunk() -> None:
    """100ms of all-zero int16 samples (1600 samples at 16 kHz) must have RMS < 1.0."""
    samples = np.zeros(1600, dtype=np.int16)  # 100ms @ 16 kHz
    chunk = samples.tobytes()
    rms = _compute_rms(chunk)
    assert rms < 1.0, f"Silent chunk RMS = {rms} — expected < 1.0"


def test_compute_rms_speech_chunk() -> None:
    """440 Hz sine wave at moderate amplitude must have RMS > 100.0."""
    sample_rate = 16_000
    duration_secs = 0.1  # 100ms
    num_samples = int(sample_rate * duration_secs)
    t = np.linspace(0, duration_secs, num_samples, endpoint=False)
    # Amplitude 5000 — well within int16 range, RMS ≈ 5000/sqrt(2) ≈ 3535
    sine = (5000.0 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    chunk = sine.tobytes()
    rms = _compute_rms(chunk)
    assert rms > 100.0, f"Speech chunk RMS = {rms} — expected > 100.0"


# ─── VAD threshold — energy gating ───────────────────────────────────────────


def test_vad_threshold_exceeded_by_high_energy_chunk() -> None:
    """A chunk with RMS > vad_threshold (500.0) must register as above-threshold.

    This validates the VAD energy gate used by _process_audio_chunk without
    requiring a full integration through the VAD state machine.
    """
    settings = Settings()

    # Build a chunk whose RMS is well above the default threshold of 500
    samples = np.full(160, 2000, dtype=np.int16)  # constant amplitude 2000 → RMS = 2000
    chunk = samples.tobytes()

    rms = _compute_rms(chunk)
    assert rms > settings.vad_threshold, (
        f"Expected RMS {rms:.1f} > vad_threshold {settings.vad_threshold}"
    )
