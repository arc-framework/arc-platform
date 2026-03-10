"""Tests for GET /health and GET /health/deep routers.

Connectivity checks are mocked — no real LiveKit or NATS connections are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voice.health_router import _check_livekit, _check_nats, router
from voice.models_v1 import HealthCheckDetail

# ─── App factory ──────────────────────────────────────────────────────────────


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# ─── Shallow health ───────────────────────────────────────────────────────────


class TestShallowHealth:
    def test_returns_200(self) -> None:
        client = TestClient(_build_app())
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_ok_status(self) -> None:
        client = TestClient(_build_app())
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_does_not_call_livekit(self) -> None:
        """Shallow health must never touch external dependencies."""
        with patch("voice.health_router._check_livekit") as mock_lk:
            client = TestClient(_build_app())
            client.get("/health")
            mock_lk.assert_not_called()

    def test_does_not_call_nats(self) -> None:
        with patch("voice.health_router._check_nats") as mock_nats:
            client = TestClient(_build_app())
            client.get("/health")
            mock_nats.assert_not_called()


# ─── Deep health — all dependencies up ───────────────────────────────────────


class TestDeepHealthAllOk:
    def _ok_detail(self) -> HealthCheckDetail:
        return HealthCheckDetail(status="ok", latency_ms=5.0)

    def test_returns_200(self) -> None:
        ok = self._ok_detail()
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=ok)),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=ok)),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.status_code == 200

    def test_overall_status_is_ok(self) -> None:
        ok = self._ok_detail()
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=ok)),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=ok)),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.json()["status"] == "ok"

    def test_checks_dict_contains_both_services(self) -> None:
        ok = self._ok_detail()
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=ok)),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=ok)),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert "arc-realtime" in body["checks"]
        assert "arc-messaging" in body["checks"]

    def test_check_details_have_ok_status(self) -> None:
        ok = self._ok_detail()
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=ok)),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=ok)),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["checks"]["arc-realtime"]["status"] == "ok"
        assert body["checks"]["arc-messaging"]["status"] == "ok"


# ─── Deep health — LiveKit down ───────────────────────────────────────────────


class TestDeepHealthLiveKitDown:
    def _degraded(self, reason: str = "connection refused") -> HealthCheckDetail:
        return HealthCheckDetail(status="degraded", reason=reason, latency_ms=10.0)

    def _ok(self) -> HealthCheckDetail:
        return HealthCheckDetail(status="ok", latency_ms=5.0)

    def test_returns_200_not_5xx(self) -> None:
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=self._degraded()),
            ),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=self._ok())),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.status_code == 200

    def test_overall_status_is_degraded(self) -> None:
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=self._degraded()),
            ),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=self._ok())),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["status"] == "degraded"

    def test_realtime_check_reports_failure_reason(self) -> None:
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=self._degraded("connection refused")),
            ),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=self._ok())),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        check = body["checks"]["arc-realtime"]
        assert check["status"] == "degraded"
        assert "connection refused" in check["reason"]

    def test_messaging_check_still_ok(self) -> None:
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=self._degraded()),
            ),
            patch("voice.health_router._check_nats", new=AsyncMock(return_value=self._ok())),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["checks"]["arc-messaging"]["status"] == "ok"


# ─── Deep health — NATS down ──────────────────────────────────────────────────


class TestDeepHealthNatsDown:
    def _degraded(self, reason: str = "connection refused") -> HealthCheckDetail:
        return HealthCheckDetail(status="degraded", reason=reason, latency_ms=10.0)

    def _ok(self) -> HealthCheckDetail:
        return HealthCheckDetail(status="ok", latency_ms=5.0)

    def test_returns_200_not_5xx(self) -> None:
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=self._ok())),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=self._degraded()),
            ),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.status_code == 200

    def test_overall_status_is_degraded(self) -> None:
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=self._ok())),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=self._degraded()),
            ),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["status"] == "degraded"

    def test_messaging_check_reports_failure_reason(self) -> None:
        with (
            patch("voice.health_router._check_livekit", new=AsyncMock(return_value=self._ok())),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=self._degraded("nats: connection refused")),
            ),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        check = body["checks"]["arc-messaging"]
        assert check["status"] == "degraded"
        assert "nats" in check["reason"]


# ─── Deep health — both down ──────────────────────────────────────────────────


class TestDeepHealthBothDown:
    def _degraded(self) -> HealthCheckDetail:
        return HealthCheckDetail(status="degraded", reason="connection refused", latency_ms=2000.0)

    def test_returns_200(self) -> None:
        degraded = self._degraded()
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=degraded),
            ),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=degraded),
            ),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.status_code == 200

    def test_overall_status_is_degraded(self) -> None:
        degraded = self._degraded()
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=degraded),
            ),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=degraded),
            ),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["status"] == "degraded"

    def test_both_checks_report_degraded(self) -> None:
        degraded = self._degraded()
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=degraded),
            ),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=degraded),
            ),
        ):
            client = TestClient(_build_app())
            body = client.get("/health/deep").json()
        assert body["checks"]["arc-realtime"]["status"] == "degraded"
        assert body["checks"]["arc-messaging"]["status"] == "degraded"

    def test_never_returns_5xx(self) -> None:
        """Guarantee no 5xx even when both dependencies are down."""
        degraded = self._degraded()
        with (
            patch(
                "voice.health_router._check_livekit",
                new=AsyncMock(return_value=degraded),
            ),
            patch(
                "voice.health_router._check_nats",
                new=AsyncMock(return_value=degraded),
            ),
        ):
            client = TestClient(_build_app())
            response = client.get("/health/deep")
        assert response.status_code < 500


# ─── Unit: _check_livekit helper ─────────────────────────────────────────────


class TestCheckLivekitUnit:
    @pytest.mark.asyncio
    async def test_ok_when_connection_succeeds(self) -> None:
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "voice.health_router.asyncio.open_connection",
            new=AsyncMock(return_value=(MagicMock(), mock_writer)),
        ):
            detail = await _check_livekit("ws://arc-realtime:7880")

        assert detail.status == "ok"
        assert detail.latency_ms is not None
        assert detail.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_degraded_when_os_error(self) -> None:
        with patch(
            "voice.health_router.asyncio.open_connection",
            new=AsyncMock(side_effect=OSError("connection refused")),
        ):
            detail = await _check_livekit("ws://arc-realtime:7880")

        assert detail.status == "degraded"
        assert detail.reason is not None
        assert "connection refused" in detail.reason

    @pytest.mark.asyncio
    async def test_degraded_on_timeout(self) -> None:
        with patch(
            "voice.health_router.asyncio.open_connection",
            new=AsyncMock(side_effect=TimeoutError()),
        ):
            detail = await _check_livekit("ws://arc-realtime:7880")

        assert detail.status == "degraded"
        assert detail.reason == "timeout"

    @pytest.mark.asyncio
    async def test_parses_wss_url_port(self) -> None:
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        captured: list[tuple[str, int]] = []

        async def fake_open(host: str, port: int) -> tuple[MagicMock, MagicMock]:
            captured.append((host, port))
            return MagicMock(), mock_writer

        with patch("voice.health_router.asyncio.open_connection", new=fake_open):
            await _check_livekit("wss://livekit.example.com:8443")

        assert captured == [("livekit.example.com", 8443)]


# ─── Unit: _check_nats helper ─────────────────────────────────────────────────


class TestCheckNatsUnit:
    @pytest.mark.asyncio
    async def test_ok_when_connect_succeeds(self) -> None:
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()

        with patch("voice.health_router.nats.connect", new=AsyncMock(return_value=mock_nc)):
            detail = await _check_nats("nats://arc-messaging:4222")

        assert detail.status == "ok"
        assert detail.latency_ms is not None

    @pytest.mark.asyncio
    async def test_degraded_on_exception(self) -> None:
        with patch(
            "voice.health_router.nats.connect",
            new=AsyncMock(side_effect=Exception("connection refused")),
        ):
            detail = await _check_nats("nats://arc-messaging:4222")

        assert detail.status == "degraded"
        assert detail.reason is not None
        assert "connection refused" in detail.reason

    @pytest.mark.asyncio
    async def test_degraded_on_timeout(self) -> None:
        with patch(
            "voice.health_router.nats.connect",
            new=AsyncMock(side_effect=TimeoutError()),
        ):
            detail = await _check_nats("nats://arc-messaging:4222")

        assert detail.status == "degraded"
        assert detail.reason == "timeout"

    @pytest.mark.asyncio
    async def test_closes_connection_on_success(self) -> None:
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()

        with patch("voice.health_router.nats.connect", new=AsyncMock(return_value=mock_nc)):
            await _check_nats("nats://arc-messaging:4222")

        mock_nc.close.assert_awaited_once()
