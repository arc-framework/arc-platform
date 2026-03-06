"""Tests for voice/main.py — FastAPI app factory and lifespan.

All external connections (NATS, Pulsar, WhisperSTT, PiperTTS, LiveKit worker,
OTEL setup) are mocked so tests run without any real infrastructure.

Route structure tests use httpx.AsyncClient (no lifespan needed — just route introspection).
Lifespan startup/shutdown tests use starlette.testclient.TestClient which correctly
sends ASGI lifespan events to the application.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient


# ─── Shared mock helpers ──────────────────────────────────────────────────────


def _mock_worker() -> MagicMock:
    """Return a MagicMock VoiceAgentWorker with async run() and stop()."""
    worker = MagicMock()
    worker.run = AsyncMock(return_value=None)
    worker.stop = AsyncMock(return_value=None)
    return worker


def _mock_publisher() -> MagicMock:
    publisher = MagicMock()
    publisher.connect = MagicMock()
    publisher.disconnect = MagicMock()
    return publisher


@contextmanager
def _patched_lifespan(
    worker: MagicMock | None = None,
    publisher: MagicMock | None = None,
    mock_telemetry: bool = True,
) -> Generator[dict[str, MagicMock], None, None]:
    """Context manager that patches all lifespan deps and yields the mocks."""
    if worker is None:
        worker = _mock_worker()
    if publisher is None:
        publisher = _mock_publisher()

    mock_nats_connect = AsyncMock()
    mock_nats_disconnect = AsyncMock()
    mock_tele = MagicMock()

    patches = [
        patch("voice.main.VoiceEventPublisher", return_value=publisher),
        patch("voice.main.WhisperSTTAdapter", return_value=MagicMock()),
        patch("voice.main.PiperTTSAdapter", return_value=MagicMock()),
        patch("voice.main.NATSBridge", return_value=MagicMock()),
        patch("voice.main.VoiceAgentWorker", return_value=worker),
        patch("voice.main.nats_connect", new=mock_nats_connect),
        patch("voice.main.nats_disconnect", new=mock_nats_disconnect),
    ]
    if mock_telemetry:
        patches.append(patch("voice.main.setup_telemetry", mock_tele))

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        if mock_telemetry:
            with patches[7]:
                yield {
                    "worker": worker,
                    "publisher": publisher,
                    "nats_connect": mock_nats_connect,
                    "nats_disconnect": mock_nats_disconnect,
                    "setup_telemetry": mock_tele,
                }
        else:
            yield {
                "worker": worker,
                "publisher": publisher,
                "nats_connect": mock_nats_connect,
                "nats_disconnect": mock_nats_disconnect,
                "setup_telemetry": mock_tele,
            }


# ─── Tests: app factory structure ─────────────────────────────────────────────


class TestCreateApp:
    def test_returns_fastapi_instance(self) -> None:
        """create_app() must return a FastAPI object."""
        from voice.main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title(self) -> None:
        from voice.main import create_app

        app = create_app()
        assert app.title == "arc-voice-agent"

    def test_app_version(self) -> None:
        from voice.main import create_app

        app = create_app()
        assert app.version == "0.1.0"

    def test_stt_route_registered(self) -> None:
        """POST /v1/audio/transcriptions must appear in the route table."""
        from voice.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/v1/audio/transcriptions" in paths

    def test_tts_route_registered(self) -> None:
        """POST /v1/audio/speech must appear in the route table."""
        from voice.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/v1/audio/speech" in paths

    def test_health_route_registered(self) -> None:
        from voice.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/health" in paths

    def test_health_deep_route_registered(self) -> None:
        from voice.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/health/deep" in paths

    def test_all_three_routers_mounted(self) -> None:
        """All required routes are present."""
        from voice.main import create_app

        app = create_app()
        paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
        required = {"/v1/audio/transcriptions", "/v1/audio/speech", "/health", "/health/deep"}
        assert required.issubset(paths)


# ─── Tests: lifespan via starlette TestClient ─────────────────────────────────


class TestLifespan:
    def test_health_returns_200_after_startup(self) -> None:
        """The /health route must respond 200 after lifespan startup completes."""
        from voice.main import create_app

        with _patched_lifespan() as _mocks:
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
        assert response.status_code == 200

    def test_nats_connect_called_on_startup(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app) as client:
                client.get("/health")

        mocks["nats_connect"].assert_awaited_once()

    def test_nats_disconnect_called_on_shutdown(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app):
                pass  # lifespan tears down when context exits

        mocks["nats_disconnect"].assert_awaited_once()

    def test_worker_stop_called_on_shutdown(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app):
                pass

        mocks["worker"].stop.assert_awaited_once()

    def test_pulsar_publisher_connected_on_startup(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app):
                pass

        mocks["publisher"].connect.assert_called_once()

    def test_pulsar_publisher_disconnected_on_shutdown(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app):
                pass

        mocks["publisher"].disconnect.assert_called_once()

    def test_setup_telemetry_called_on_startup(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app):
                pass

        mocks["setup_telemetry"].assert_called_once()

    def test_worker_run_called_on_startup(self) -> None:
        from voice.main import create_app

        with _patched_lifespan() as mocks:
            app = create_app()
            with TestClient(app) as client:
                client.get("/health")

        mocks["worker"].run.assert_awaited_once()

    def test_worker_timeout_logs_and_continues(self) -> None:
        """Shutdown must complete without raising even when the worker hangs past the timeout."""
        from voice.main import create_app

        # A worker whose run() hangs forever; stop() does nothing
        hanging_worker: MagicMock = MagicMock()
        hanging_worker.stop = AsyncMock(return_value=None)

        async def _hang() -> None:
            await asyncio.sleep(9999)

        hanging_worker.run = AsyncMock(side_effect=_hang)
        publisher = _mock_publisher()

        with (
            _patched_lifespan(worker=hanging_worker, publisher=publisher) as mocks,
            patch("voice.main._WORKER_SHUTDOWN_TIMEOUT_S", 0.05),
        ):
            app = create_app()
            # TestClient should complete shutdown without hanging or raising
            with TestClient(app):
                pass

        # Pulsar and NATS must still be torn down even after worker timeout
        mocks["publisher"].disconnect.assert_called_once()
        mocks["nats_disconnect"].assert_awaited_once()
