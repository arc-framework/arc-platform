"""Tests for VoiceEventPublisher — fire-and-forget Pulsar event publishing."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from voice.models_v1 import (
    VoiceSessionEndedEvent,
    VoiceSessionStartedEvent,
    VoiceTurnCompletedEvent,
    VoiceTurnFailedEvent,
)
from voice.pulsar_events import (
    TOPIC_SESSION_ENDED,
    TOPIC_SESSION_STARTED,
    TOPIC_TURN_COMPLETED,
    TOPIC_TURN_FAILED,
    VoiceEventPublisher,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def publisher() -> VoiceEventPublisher:
    return VoiceEventPublisher()


@pytest.fixture()
def session_started_event() -> VoiceSessionStartedEvent:
    return VoiceSessionStartedEvent(
        session_id="sess-1",
        room_id="room-1",
        correlation_id="corr-1",
        participant_identity="user@example.com",
    )


@pytest.fixture()
def session_ended_event() -> VoiceSessionEndedEvent:
    return VoiceSessionEndedEvent(
        session_id="sess-1",
        room_id="room-1",
        correlation_id="corr-1",
        duration_secs=42.5,
    )


@pytest.fixture()
def turn_completed_event() -> VoiceTurnCompletedEvent:
    return VoiceTurnCompletedEvent(
        session_id="sess-1",
        room_id="room-1",
        correlation_id="corr-1",
        transcript="Hello world",
        response_preview="Hi there",
        stt_latency_ms=100.0,
        bridge_latency_ms=200.0,
        tts_latency_ms=50.0,
        total_latency_ms=350.0,
    )


@pytest.fixture()
def turn_failed_event() -> VoiceTurnFailedEvent:
    return VoiceTurnFailedEvent(
        session_id="sess-1",
        room_id="room-1",
        correlation_id="corr-1",
        error_type="stt_error",
        error_message="STT model unavailable",
    )


# ─── connect / disconnect ─────────────────────────────────────────────────────


def test_connect_creates_client_and_producers(publisher: VoiceEventPublisher) -> None:
    mock_client = MagicMock()
    mock_producer = MagicMock()
    mock_client.create_producer.return_value = mock_producer

    with patch("voice.pulsar_events.pulsar.Client", return_value=mock_client) as mock_cls:
        publisher.connect("pulsar://localhost:6650")

    mock_cls.assert_called_once_with("pulsar://localhost:6650")
    assert mock_client.create_producer.call_count == 4
    mock_client.create_producer.assert_any_call(TOPIC_SESSION_STARTED)
    mock_client.create_producer.assert_any_call(TOPIC_SESSION_ENDED)
    mock_client.create_producer.assert_any_call(TOPIC_TURN_COMPLETED)
    mock_client.create_producer.assert_any_call(TOPIC_TURN_FAILED)


def test_connect_pulsar_unavailable_does_not_raise(publisher: VoiceEventPublisher) -> None:
    with patch("voice.pulsar_events.pulsar.Client", side_effect=Exception("connection refused")):
        publisher.connect("pulsar://bad-host:6650")  # must not raise

    assert publisher._client is None
    assert publisher._producers == {}


def test_disconnect_closes_producers_and_client(publisher: VoiceEventPublisher) -> None:
    mock_client = MagicMock()
    mock_producer = MagicMock()
    mock_client.create_producer.return_value = mock_producer

    with patch("voice.pulsar_events.pulsar.Client", return_value=mock_client):
        publisher.connect("pulsar://localhost:6650")

    publisher.disconnect()

    assert mock_producer.close.call_count == 4
    mock_client.close.assert_called_once()
    assert publisher._producers == {}
    assert publisher._client is None


def test_disconnect_tolerates_producer_close_error(publisher: VoiceEventPublisher) -> None:
    mock_client = MagicMock()
    mock_producer = MagicMock()
    mock_producer.close.side_effect = Exception("already closed")
    mock_client.create_producer.return_value = mock_producer

    with patch("voice.pulsar_events.pulsar.Client", return_value=mock_client):
        publisher.connect("pulsar://localhost:6650")

    publisher.disconnect()  # must not raise


# ─── Fire-and-forget behaviour ────────────────────────────────────────────────


async def test_publish_session_started_fire_and_forget(
    publisher: VoiceEventPublisher,
    session_started_event: VoiceSessionStartedEvent,
) -> None:
    mock_producer = MagicMock()
    publisher._producers[TOPIC_SESSION_STARTED] = mock_producer

    publisher.publish_session_started(session_started_event)

    # Task has not run yet — send not called
    mock_producer.send.assert_not_called()

    # Drain the event loop so the task runs
    await asyncio.sleep(0)

    mock_producer.send.assert_called_once()
    payload = json.loads(mock_producer.send.call_args[0][0])
    assert payload["session_id"] == "sess-1"
    assert payload["participant_identity"] == "user@example.com"


async def test_publish_session_ended_fire_and_forget(
    publisher: VoiceEventPublisher,
    session_ended_event: VoiceSessionEndedEvent,
) -> None:
    mock_producer = MagicMock()
    publisher._producers[TOPIC_SESSION_ENDED] = mock_producer

    publisher.publish_session_ended(session_ended_event)
    mock_producer.send.assert_not_called()

    await asyncio.sleep(0)

    mock_producer.send.assert_called_once()
    payload = json.loads(mock_producer.send.call_args[0][0])
    assert payload["session_id"] == "sess-1"
    assert payload["duration_secs"] == 42.5


async def test_publish_turn_completed_fire_and_forget(
    publisher: VoiceEventPublisher,
    turn_completed_event: VoiceTurnCompletedEvent,
) -> None:
    mock_producer = MagicMock()
    publisher._producers[TOPIC_TURN_COMPLETED] = mock_producer

    publisher.publish_turn_completed(turn_completed_event)
    mock_producer.send.assert_not_called()

    await asyncio.sleep(0)

    mock_producer.send.assert_called_once()
    payload = json.loads(mock_producer.send.call_args[0][0])
    assert payload["transcript"] == "Hello world"
    assert payload["total_latency_ms"] == 350.0


async def test_publish_turn_failed_fire_and_forget(
    publisher: VoiceEventPublisher,
    turn_failed_event: VoiceTurnFailedEvent,
) -> None:
    mock_producer = MagicMock()
    publisher._producers[TOPIC_TURN_FAILED] = mock_producer

    publisher.publish_turn_failed(turn_failed_event)
    mock_producer.send.assert_not_called()

    await asyncio.sleep(0)

    mock_producer.send.assert_called_once()
    payload = json.loads(mock_producer.send.call_args[0][0])
    assert payload["error_type"] == "stt_error"
    assert payload["error_message"] == "STT model unavailable"


# ─── Fail-open: producer send failure does not raise ─────────────────────────


async def test_publish_send_failure_does_not_raise(
    publisher: VoiceEventPublisher,
    session_started_event: VoiceSessionStartedEvent,
) -> None:
    mock_producer = MagicMock()
    mock_producer.send.side_effect = Exception("Pulsar unavailable")
    publisher._producers[TOPIC_SESSION_STARTED] = mock_producer

    publisher.publish_session_started(session_started_event)
    await asyncio.sleep(0)  # drain task — must not raise


async def test_publish_no_producer_does_not_raise(
    publisher: VoiceEventPublisher,
    session_started_event: VoiceSessionStartedEvent,
) -> None:
    # _producers is empty — no producer for any topic
    publisher.publish_session_started(session_started_event)
    await asyncio.sleep(0)  # must not raise


# ─── Payload integrity: no secrets, no raw audio ─────────────────────────────


async def test_turn_completed_payload_has_no_raw_audio(
    publisher: VoiceEventPublisher,
    turn_completed_event: VoiceTurnCompletedEvent,
) -> None:
    mock_producer = MagicMock()
    publisher._producers[TOPIC_TURN_COMPLETED] = mock_producer

    publisher.publish_turn_completed(turn_completed_event)
    await asyncio.sleep(0)

    raw_payload = mock_producer.send.call_args[0][0]
    # response_preview is a text preview — check it is not raw bytes
    assert isinstance(raw_payload, bytes)
    payload = json.loads(raw_payload)
    # Must contain a short text preview, not a bytes blob
    assert len(payload["response_preview"]) <= 200
