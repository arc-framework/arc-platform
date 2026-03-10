"""Hexagonal architecture port interfaces for arc-voice-agent.

STTPort, TTSPort, LLMBridgePort are runtime_checkable Protocols so adapters can
be verified with isinstance() at startup without coupling to a specific base class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ─── Result Types ──────────────────────────────────────────────────────────────


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_secs: float


@dataclass
class SynthesisResult:
    wav_bytes: bytes
    sample_rate: int
    duration_secs: float


# ─── Custom Exceptions ─────────────────────────────────────────────────────────


class STTError(Exception):
    """Raised by STTPort implementations on transcription failure."""


class TTSError(Exception):
    """Raised by TTSPort implementations on synthesis failure."""


class BridgeError(Exception):
    """Raised by LLMBridgePort on NATS timeout or reasoner error.

    is_timeout distinguishes the two failure modes so the worker can set the
    correct VoiceTurnFailedEvent.error_type:
      is_timeout=True  → 'bridge_timeout'
      is_timeout=False → 'bridge_error'
    """

    def __init__(
        self,
        message: str,
        *,
        is_timeout: bool,
        error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.is_timeout = is_timeout
        # Allow explicit override; default is derived from is_timeout.
        self.error_type: str = error_type if error_type is not None else (
            "bridge_timeout" if is_timeout else "bridge_error"
        )


# ─── Port Protocols ────────────────────────────────────────────────────────────


@runtime_checkable
class STTPort(Protocol):
    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptResult: ...


@runtime_checkable
class TTSPort(Protocol):
    async def synthesize(self, text: str, voice: str) -> SynthesisResult: ...


@runtime_checkable
class LLMBridgePort(Protocol):
    async def reason(
        self, transcript: str, session_id: str, correlation_id: str
    ) -> str: ...
