"""Durable voice lifecycle event publisher to arc-streaming (Pulsar).

Publishes fire-and-forget events for voice session and turn lifecycle.
Pulsar unavailability logs a warning and returns without raising — fail-open
so the voice pipeline is never blocked by the event bus.

Topics:
    arc.voice.session.started
    arc.voice.session.ended
    arc.voice.turn.completed
    arc.voice.turn.failed
"""

from __future__ import annotations

import asyncio
from typing import Any

import pulsar
import structlog

from voice.models_v1 import (
    VoiceSessionEndedEvent,
    VoiceSessionStartedEvent,
    VoiceTurnCompletedEvent,
    VoiceTurnFailedEvent,
)

_log = structlog.get_logger(__name__)

TOPIC_SESSION_STARTED = "arc.voice.session.started"
TOPIC_SESSION_ENDED = "arc.voice.session.ended"
TOPIC_TURN_COMPLETED = "arc.voice.turn.completed"
TOPIC_TURN_FAILED = "arc.voice.turn.failed"


class VoiceEventPublisher:
    """Wraps a Pulsar client and exposes fire-and-forget voice event publishing.

    Each publish method wraps the actual send in asyncio.create_task() so the
    caller is never blocked waiting for Pulsar I/O.  If the Pulsar client or
    producer raises for any reason the exception is caught, a warning is logged,
    and the method returns normally (fail-open).
    """

    def __init__(self) -> None:
        self._client: pulsar.Client | None = None
        self._producers: dict[str, Any] = {}

    def connect(self, pulsar_url: str) -> None:
        """Create Pulsar client and producer pool for all voice topics."""
        try:
            self._client = pulsar.Client(pulsar_url)
            for topic in (
                TOPIC_SESSION_STARTED,
                TOPIC_SESSION_ENDED,
                TOPIC_TURN_COMPLETED,
                TOPIC_TURN_FAILED,
            ):
                self._producers[topic] = self._client.create_producer(topic)
            _log.info("pulsar_events connected", url=pulsar_url)
        except Exception as exc:
            _log.warning("pulsar_events connect failed", error=str(exc))
            self._client = None
            self._producers = {}

    def disconnect(self) -> None:
        """Close all producers and the Pulsar client."""
        for topic, producer in self._producers.items():
            try:
                producer.close()
            except Exception as exc:
                _log.warning("pulsar_events producer close failed", topic=topic, error=str(exc))
        self._producers = {}

        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                _log.warning("pulsar_events client close failed", error=str(exc))
            self._client = None

        _log.info("pulsar_events disconnected")

    async def _send(self, topic: str, payload: bytes) -> None:
        """Send payload to a Pulsar topic (best-effort, never raises)."""
        producer = self._producers.get(topic)
        if producer is None:
            _log.warning("pulsar_events no producer for topic", topic=topic)
            return
        try:
            await asyncio.get_running_loop().run_in_executor(None, producer.send, payload)
        except Exception as exc:
            _log.warning("pulsar_events publish failed", topic=topic, error=str(exc))

    def publish_session_started(self, event: VoiceSessionStartedEvent) -> None:
        """Fire-and-forget publish to arc.voice.session.started."""
        asyncio.create_task(
            self._send(TOPIC_SESSION_STARTED, event.model_dump_json().encode())
        )

    def publish_session_ended(self, event: VoiceSessionEndedEvent) -> None:
        """Fire-and-forget publish to arc.voice.session.ended."""
        asyncio.create_task(
            self._send(TOPIC_SESSION_ENDED, event.model_dump_json().encode())
        )

    def publish_turn_completed(self, event: VoiceTurnCompletedEvent) -> None:
        """Fire-and-forget publish to arc.voice.turn.completed."""
        asyncio.create_task(
            self._send(TOPIC_TURN_COMPLETED, event.model_dump_json().encode())
        )

    def publish_turn_failed(self, event: VoiceTurnFailedEvent) -> None:
        """Fire-and-forget publish to arc.voice.turn.failed."""
        asyncio.create_task(
            self._send(TOPIC_TURN_FAILED, event.model_dump_json().encode())
        )
