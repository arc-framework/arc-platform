"""FastAPI router for GET /health and GET /health/deep."""

from __future__ import annotations

import asyncio
import contextlib
import time
from urllib.parse import urlparse

import nats
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from voice.config import Settings
from voice.models_v1 import HealthCheckDetail, HealthCheckResponse

router = APIRouter()

_CHECK_TIMEOUT_S = 2.0


def get_settings() -> Settings:
    return Settings()


# ─── Shallow health ───────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> JSONResponse:
    """Return 200 immediately when the process is alive.

    No dependency checks — always fast.
    """
    return JSONResponse(status_code=200, content={"status": "ok"})


# ─── Deep health ──────────────────────────────────────────────────────────────


async def _check_livekit(livekit_url: str) -> HealthCheckDetail:
    """TCP ping to LiveKit server.  Parses host/port from the ws(s):// URL."""
    parsed = urlparse(livekit_url)
    host = parsed.hostname or "arc-realtime"
    port = parsed.port or (443 if parsed.scheme in ("wss", "https") else 80)

    t0 = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=_CHECK_TIMEOUT_S,
        )
        writer.close()
        await writer.wait_closed()
    except TimeoutError:
        return HealthCheckDetail(
            status="degraded",
            reason="timeout",
            latency_ms=_CHECK_TIMEOUT_S * 1000,
        )
    except OSError as exc:
        return HealthCheckDetail(
            status="degraded",
            reason=str(exc),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    return HealthCheckDetail(
        status="ok",
        latency_ms=(time.perf_counter() - t0) * 1000,
    )


async def _check_nats(nats_url: str) -> HealthCheckDetail:
    """NATS connect ping.  Reports degraded on any failure."""
    t0 = time.perf_counter()
    nc = None
    try:
        nc = await asyncio.wait_for(
            nats.connect(nats_url, connect_timeout=_CHECK_TIMEOUT_S),
            timeout=_CHECK_TIMEOUT_S + 0.5,
        )
    except TimeoutError:
        return HealthCheckDetail(
            status="degraded",
            reason="timeout",
            latency_ms=_CHECK_TIMEOUT_S * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckDetail(
            status="degraded",
            reason=str(exc),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    finally:
        if nc is not None:
            with contextlib.suppress(Exception):
                await nc.close()

    return HealthCheckDetail(
        status="ok",
        latency_ms=(time.perf_counter() - t0) * 1000,
    )


@router.get("/health/deep")
async def health_deep() -> JSONResponse:
    """Check arc-realtime (LiveKit) and arc-messaging (NATS) connectivity.

    Always returns HTTP 200.  The ``status`` field in the body indicates
    overall health: ``"ok"`` only when all checks pass, ``"degraded"``
    when any dependency is unreachable.
    """
    settings = get_settings()

    nats_url = "nats://arc-messaging:4222"

    livekit_detail, nats_detail = await asyncio.gather(
        _check_livekit(settings.livekit_url),
        _check_nats(nats_url),
    )

    checks: dict[str, HealthCheckDetail] = {
        "arc-realtime": livekit_detail,
        "arc-messaging": nats_detail,
    }

    all_ok = all(d.status == "ok" for d in checks.values())
    overall: str = "ok" if all_ok else "degraded"

    body = HealthCheckResponse(status=overall, checks=checks)
    return JSONResponse(status_code=200, content=body.model_dump())
