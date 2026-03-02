from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sherlock.main import AppState, app
from sherlock.memory import SherlockMemory
from sherlock.nats_handler import NATSHandler
from sherlock.observability import SherlockMetrics


@pytest.fixture
def mock_memory() -> AsyncMock:
    """Mock SherlockMemory with sensible defaults."""
    m = AsyncMock(spec=SherlockMemory)
    m.search.return_value = ["ctx1", "ctx2"]
    m.save.return_value = None
    m.health_check.return_value = {"qdrant": True, "postgres": True}
    m.init.return_value = None
    return m


@pytest.fixture
def mock_graph() -> MagicMock:
    """Mock compiled LangGraph that returns a fixed response string."""
    g = MagicMock()
    # ainvoke returns a state dict with final_response populated
    g.ainvoke = AsyncMock(
        return_value={
            "messages": [],
            "user_id": "test-user",
            "context": ["ctx1"],
            "final_response": "mocked response",
            "error_count": 0,
        }
    )
    return g


@pytest.fixture
def mock_nats() -> MagicMock:
    """Mock NATSHandler that reports as connected."""
    n = MagicMock(spec=NATSHandler)
    n.is_connected.return_value = True
    return n


@pytest.fixture
def mock_metrics() -> MagicMock:
    """Mock SherlockMetrics with no-op instruments."""
    m = MagicMock(spec=SherlockMetrics)
    m.requests_total = MagicMock()
    m.requests_total.add = MagicMock()
    m.errors_total = MagicMock()
    m.errors_total.add = MagicMock()
    m.latency = MagicMock()
    m.latency.record = MagicMock()
    m.context_size = MagicMock()
    m.context_size.record = MagicMock()
    return m


@pytest.fixture
def app_state(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
    mock_nats: MagicMock,
    mock_metrics: MagicMock,
) -> AppState:
    """Fully-populated AppState using mocks (no live services)."""
    return AppState(
        memory=mock_memory,
        graph=mock_graph,
        nats=mock_nats,
        metrics=mock_metrics,
        pulsar=None,
    )


@pytest_asyncio.fixture
async def test_client(app_state: AppState) -> Any:
    """httpx.AsyncClient wrapping the FastAPI app with AppState injected."""
    app.state.app_state = app_state
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
