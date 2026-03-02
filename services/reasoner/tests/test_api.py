from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import AsyncMock, patch

import jsonschema
import pytest
import yaml


# ─── Happy path ───────────────────────────────────────────────────────────────


async def test_chat_happy_path(test_client: Any) -> None:
    with patch("sherlock.main.invoke_graph", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "mocked response"
        response = await test_client.post(
            "/chat", json={"user_id": "u1", "text": "hello"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "u1"
    assert body["text"] == "mocked response"
    assert isinstance(body["latency_ms"], int)


# ─── Validation errors ────────────────────────────────────────────────────────


async def test_chat_422_missing_user_id(test_client: Any) -> None:
    response = await test_client.post("/chat", json={"text": "hello"})
    assert response.status_code == 422


async def test_chat_422_empty_text(test_client: Any) -> None:
    response = await test_client.post(
        "/chat", json={"user_id": "u1", "text": ""}
    )
    assert response.status_code == 422


# ─── Service not ready ────────────────────────────────────────────────────────


async def test_chat_503_service_not_ready(test_client: Any) -> None:
    from sherlock.main import app

    # Remove app_state so the endpoint cannot reach it
    del app.state.app_state

    try:
        response = await test_client.post(
            "/chat", json={"user_id": "u1", "text": "hello"}
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Service not ready"}
    finally:
        # Restore so other tests are not affected (fixture resets between tests,
        # but guard against same-session leakage)
        pass


# ─── Health endpoints ─────────────────────────────────────────────────────────


async def test_health_200(test_client: Any) -> None:
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_deep_all_healthy(test_client: Any) -> None:
    response = await test_client.get("/health/deep")
    assert response.status_code == 200
    body = response.json()
    components = body["components"]
    assert components["qdrant"] is True
    assert components["postgres"] is True
    assert components["nats"] is True


async def test_health_deep_qdrant_down(
    test_client: Any, app_state: Any
) -> None:
    # Override memory.health_check to report qdrant as down
    app_state.memory.health_check = AsyncMock(
        return_value={"qdrant": False, "postgres": True}
    )

    response = await test_client.get("/health/deep")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"


# ─── OpenAPI schema validation (GAP-2) ───────────────────────────────────────


async def test_chat_response_matches_openapi_schema(test_client: Any) -> None:
    contracts_dir = (
        pathlib.Path(__file__).parent.parent / "contracts" / "openapi.yaml"
    )

    with contracts_dir.open() as fh:
        spec = yaml.safe_load(fh)

    chat_response_schema = spec["components"]["schemas"]["ChatResponse"]

    with patch("sherlock.main.invoke_graph", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "mocked response"
        response = await test_client.post(
            "/chat", json={"user_id": "u1", "text": "hello"}
        )

    assert response.status_code == 200
    jsonschema.validate(instance=response.json(), schema=chat_response_schema)


# ─── Marker sanity (ensure asyncio_mode=auto picked up) ──────────────────────
# No explicit @pytest.mark.asyncio needed — pyproject.toml sets asyncio_mode = "auto"
