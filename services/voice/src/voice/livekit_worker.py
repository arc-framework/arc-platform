"""LiveKit voice agent worker for arc-voice-agent (Scarlett).

Connects to a LiveKit room as an agent participant, processes audio through a
VAD → STT → LLM bridge → TTS → publish pipeline, and emits lifecycle events.

Architecture: hexagonal — depends on STTPort, TTSPort, LLMBridgePort interfaces.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum, auto

import livekit.rtc as rtc
import numpy as np
import structlog

from voice.config import Settings
from voice.interfaces import BridgeError, LLMBridgePort, STTError, STTPort, TTSError, TTSPort
from voice.models_v1 import (
    VoiceSessionEndedEvent,
    VoiceSessionStartedEvent,
    VoiceTurnCompletedEvent,
    VoiceTurnFailedEvent,
)
from voice.observability import get_tracer, turn_latency
from voice.pulsar_events import VoiceEventPublisher

_log = structlog.get_logger(__name__)

# ─── VAD constants ────────────────────────────────────────────────────────────

_AUDIO_SAMPLE_RATE = 16_000
_AUDIO_CHANNELS = 1

# ─── VAD state ────────────────────────────────────────────────────────────────


class _VadState(Enum):
    SILENT = auto()
    SPEAKING = auto()


# ─── RMS helper ───────────────────────────────────────────────────────────────


def _compute_rms(audio_chunk: bytes) -> float:
    """Compute RMS energy of 16-bit mono PCM audio chunk."""
    if not audio_chunk:
        return 0.0
    samples = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples**2)))


# ─── Worker ───────────────────────────────────────────────────────────────────


class VoiceAgentWorker:
    """Connects to LiveKit and processes voice turns via STT → bridge → TTS.

    Uses hexagonal architecture — accepts Port interfaces, not concrete adapters.
    This makes the worker fully testable with mocks.
    """

    def __init__(
        self,
        stt: STTPort,
        tts: TTSPort,
        bridge: LLMBridgePort,
        publisher: VoiceEventPublisher,
        settings: Settings,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._bridge = bridge
        self._publisher = publisher
        self._settings = settings
        self._stopped = False

        # VAD state per-session — keyed by session_id
        self._vad_state: dict[str, _VadState] = {}
        self._speech_frames: dict[str, list[bytes]] = {}
        self._silence_count: dict[str, int] = {}

    # ─── Public API ───────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Connect to LiveKit and process voice turns until stopped."""
        room = rtc.Room()
        room.on("track_subscribed", self._on_track_subscribed)
        room.on("participant_connected", self._on_participant_connected)
        room.on("participant_disconnected", self._on_participant_disconnected)

        try:
            if not self._stopped:
                token = self._build_token()
                await room.connect(self._settings.livekit_url, token)
                _log.info(
                    "livekit_worker connected",
                    url=self._settings.livekit_url,
                    room=self._settings.livekit_room_name,
                )

            # Poll until stopped — room callbacks drive audio processing
            while not self._stopped:
                await asyncio.sleep(0.1)

        except Exception as exc:
            _log.error("livekit_worker run error", error=str(exc))
        finally:
            await room.disconnect()
            _log.info("livekit_worker disconnected")

    async def stop(self) -> None:
        """Signal the worker to stop gracefully."""
        self._stopped = True

    # ─── LiveKit event handlers ───────────────────────────────────────────────

    def _on_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        session_id = participant.identity or participant.sid
        room_name = self._settings.livekit_room_name
        correlation_id = str(uuid.uuid4())

        self._vad_state[session_id] = _VadState.SILENT
        self._speech_frames[session_id] = []
        self._silence_count[session_id] = 0

        self._publisher.publish_session_started(
            VoiceSessionStartedEvent(
                session_id=session_id,
                room_id=room_name,
                correlation_id=correlation_id,
                participant_identity=session_id,
            )
        )
        _log.info("livekit_worker participant connected", session_id=session_id)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        session_id = participant.identity or participant.sid
        room_name = self._settings.livekit_room_name
        correlation_id = str(uuid.uuid4())

        self._vad_state.pop(session_id, None)
        self._speech_frames.pop(session_id, None)
        self._silence_count.pop(session_id, None)

        self._publisher.publish_session_ended(
            VoiceSessionEndedEvent(
                session_id=session_id,
                room_id=room_name,
                correlation_id=correlation_id,
                duration_secs=0.0,
            )
        )
        _log.info("livekit_worker participant disconnected", session_id=session_id)

    def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        session_id = participant.identity or participant.sid
        room_name = self._settings.livekit_room_name
        asyncio.get_event_loop().create_task(
            self._consume_audio_track(track, session_id, room_name)
        )

    async def _consume_audio_track(
        self,
        track: rtc.Track,
        session_id: str,
        room_name: str,
    ) -> None:
        """Read audio frames from a subscribed track and feed them through VAD."""
        audio_stream = rtc.AudioStream(
            track,
            sample_rate=_AUDIO_SAMPLE_RATE,
            num_channels=_AUDIO_CHANNELS,
        )
        try:
            async for event in audio_stream:
                if self._stopped:
                    break
                frame: rtc.AudioFrame = event.frame
                chunk = bytes(frame.data)
                await self._process_audio_chunk(chunk, session_id, room_name)
        except Exception as exc:
            _log.warning("livekit_worker audio stream error", session_id=session_id, error=str(exc))
        finally:
            await audio_stream.aclose()

    # ─── VAD state machine ────────────────────────────────────────────────────

    async def _process_audio_chunk(
        self,
        chunk: bytes,
        session_id: str,
        room_name: str,
    ) -> None:
        """Energy-based VAD: accumulate speech frames and fire _handle_turn at turn end."""
        rms = _compute_rms(chunk)
        threshold = self._settings.vad_threshold
        silence_limit = self._settings.vad_silence_frames

        # Initialise state lazily for sessions that join without triggering connected event
        if session_id not in self._vad_state:
            self._vad_state[session_id] = _VadState.SILENT
            self._speech_frames[session_id] = []
            self._silence_count[session_id] = 0

        state = self._vad_state[session_id]

        if rms > threshold:
            # Speech detected
            self._speech_frames[session_id].append(chunk)
            self._silence_count[session_id] = 0
            if state == _VadState.SILENT:
                self._vad_state[session_id] = _VadState.SPEAKING
        else:
            # Silence
            if state == _VadState.SPEAKING:
                self._silence_count[session_id] += 1
                if self._silence_count[session_id] > silence_limit:
                    # Turn boundary reached — fire turn
                    accumulated = b"".join(self._speech_frames[session_id])
                    self._speech_frames[session_id] = []
                    self._silence_count[session_id] = 0
                    self._vad_state[session_id] = _VadState.SILENT
                    await self._handle_turn(session_id, accumulated, room_name)

    # ─── Core pipeline ────────────────────────────────────────────────────────

    async def _handle_turn(
        self,
        session_id: str,
        audio_bytes: bytes,
        room_name: str,
    ) -> None:
        """Process a single voice turn: STT → bridge → TTS → publish audio."""
        correlation_id = str(uuid.uuid4())
        turn_start = time.monotonic()

        tracer = get_tracer()
        with tracer.start_as_current_span("voice.worker.turn") as span:
            span.set_attribute("voice.session_id", session_id)
            span.set_attribute("voice.correlation_id", correlation_id)
            span.set_attribute("voice.room_name", room_name)

            try:
                # ── STT ───────────────────────────────────────────────────────
                stt_start = time.monotonic()
                try:
                    transcript_result = await self._stt.transcribe(audio_bytes, language=None)
                except STTError as exc:
                    _log.warning(
                        "livekit_worker stt error",
                        session_id=session_id,
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    self._publisher.publish_turn_failed(
                        VoiceTurnFailedEvent(
                            session_id=session_id,
                            room_id=room_name,
                            correlation_id=correlation_id,
                            error_type="stt_error",
                            error_message=str(exc),
                        )
                    )
                    return
                stt_elapsed_ms = (time.monotonic() - stt_start) * 1000.0
                transcript = transcript_result.text

                # ── Bridge ────────────────────────────────────────────────────
                bridge_start = time.monotonic()
                try:
                    response_text = await self._bridge.reason(
                        transcript, session_id, correlation_id
                    )
                except BridgeError as exc:
                    error_type = "bridge_timeout" if exc.is_timeout else "bridge_error"
                    _log.warning(
                        "livekit_worker bridge error",
                        session_id=session_id,
                        correlation_id=correlation_id,
                        error_type=error_type,
                        error=str(exc),
                    )
                    self._publisher.publish_turn_failed(
                        VoiceTurnFailedEvent(
                            session_id=session_id,
                            room_id=room_name,
                            correlation_id=correlation_id,
                            error_type=error_type,
                            error_message=str(exc),
                        )
                    )
                    return
                bridge_elapsed_ms = (time.monotonic() - bridge_start) * 1000.0

                # ── TTS ───────────────────────────────────────────────────────
                tts_start = time.monotonic()
                try:
                    synthesis = await self._tts.synthesize(response_text, voice="default")
                except TTSError as exc:
                    _log.warning(
                        "livekit_worker tts error",
                        session_id=session_id,
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    self._publisher.publish_turn_failed(
                        VoiceTurnFailedEvent(
                            session_id=session_id,
                            room_id=room_name,
                            correlation_id=correlation_id,
                            error_type="tts_error",
                            error_message=str(exc),
                        )
                    )
                    return
                tts_elapsed_ms = (time.monotonic() - tts_start) * 1000.0

                total_elapsed_ms = (time.monotonic() - turn_start) * 1000.0

                # ── Record OTEL histogram ─────────────────────────────────────
                if turn_latency is not None:
                    turn_latency.record(
                        total_elapsed_ms / 1000.0,
                        {"session_id": session_id},
                    )

                # ── Publish audio back to room ────────────────────────────────
                asyncio.get_running_loop().create_task(
                    self._publish_audio(synthesis.wav_bytes, synthesis.sample_rate)
                )

                # ── Publish lifecycle event ───────────────────────────────────
                self._publisher.publish_turn_completed(
                    VoiceTurnCompletedEvent(
                        session_id=session_id,
                        room_id=room_name,
                        correlation_id=correlation_id,
                        transcript=transcript,
                        response_preview=response_text[:200],
                        stt_latency_ms=stt_elapsed_ms,
                        bridge_latency_ms=bridge_elapsed_ms,
                        tts_latency_ms=tts_elapsed_ms,
                        total_latency_ms=total_elapsed_ms,
                    )
                )

                span.set_attribute("voice.worker.outcome", "success")
                _log.info(
                    "livekit_worker turn completed",
                    session_id=session_id,
                    correlation_id=correlation_id,
                    total_ms=total_elapsed_ms,
                )

            except Exception as exc:
                _log.error(
                    "livekit_worker unknown error",
                    session_id=session_id,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                self._publisher.publish_turn_failed(
                    VoiceTurnFailedEvent(
                        session_id=session_id,
                        room_id=room_name,
                        correlation_id=correlation_id,
                        error_type="unknown",
                        error_message=str(exc),
                    )
                )
                span.set_attribute("voice.worker.outcome", "unknown_error")

    # ─── Audio publishing ─────────────────────────────────────────────────────

    async def _publish_audio(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Publish WAV audio back to the LiveKit room via a LocalAudioTrack.

        Parses raw PCM from WAV bytes and sends it through an AudioSource.
        Errors are logged but never propagated — audio delivery is best-effort.
        """
        try:
            # Skip WAV header (44 bytes) to get raw PCM samples
            pcm_bytes = wav_bytes[44:] if len(wav_bytes) > 44 else wav_bytes
            if not pcm_bytes:
                return

            source = rtc.AudioSource(sample_rate, _AUDIO_CHANNELS)
            rtc.LocalAudioTrack.create_audio_track("agent-audio", source)

            samples_per_channel = len(pcm_bytes) // 2  # 16-bit = 2 bytes per sample
            frame = rtc.AudioFrame.create(sample_rate, _AUDIO_CHANNELS, samples_per_channel)
            frame.data[:] = pcm_bytes

            await source.capture_frame(frame)
            _log.debug("livekit_worker audio published", bytes=len(wav_bytes))

        except Exception as exc:
            _log.warning("livekit_worker audio publish failed", error=str(exc))

    # ─── Token builder ────────────────────────────────────────────────────────

    def _build_token(self) -> str:
        """Build a LiveKit access token for the agent participant.

        Uses livekit-api JWT token generation when available.
        Falls back to an empty string for test environments.
        """
        try:
            from livekit.api import AccessToken, VideoGrants

            grants = VideoGrants(
                room_join=True,
                room=self._settings.livekit_room_name,
            )
            token = (
                AccessToken(self._settings.livekit_api_key, self._settings.livekit_api_secret)
                .with_identity("arc-voice-agent")
                .with_grants(grants)
                .to_jwt()
            )
            return str(token)
        except Exception as exc:
            _log.warning("livekit_worker token build failed, using empty token", error=str(exc))
            return ""
