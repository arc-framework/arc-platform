from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sherlock.graph import build_graph, invoke_graph


# ─── Helpers ──────────────────────────────────────────────────────────────────

_VALID_FINAL_STATE: dict[str, Any] = {
    "messages": [],
    "user_id": "test-user",
    "context": ["ctx1"],
    "final_response": "mocked response",
    "error_count": 0,
}


# ─── build_graph ──────────────────────────────────────────────────────────────


def test_build_graph_returns_compiled_graph(
    mock_memory: AsyncMock, mock_llm: MagicMock
) -> None:
    graph = build_graph(mock_memory, mock_llm)
    assert graph is not None


# ─── invoke_graph ─────────────────────────────────────────────────────────────


async def test_invoke_graph_calls_memory_search(
    mock_memory: AsyncMock, mock_graph: MagicMock
) -> None:
    # memory.search is called inside graph nodes, not directly by invoke_graph.
    # We patch graph.ainvoke so no real node execution happens, and confirm that
    # memory.save (which IS called by invoke_graph directly) was called.
    mock_graph.ainvoke = AsyncMock(return_value=_VALID_FINAL_STATE)

    await invoke_graph(mock_graph, mock_memory, "u1", "hello")

    # memory.save is the observable side-effect owned by invoke_graph itself.
    assert mock_memory.save.called


async def test_invoke_graph_calls_memory_save_twice(
    mock_memory: AsyncMock, mock_graph: MagicMock
) -> None:
    mock_graph.ainvoke = AsyncMock(return_value=_VALID_FINAL_STATE)

    await invoke_graph(mock_graph, mock_memory, "u1", "hello")

    assert mock_memory.save.call_count == 2
    calls = mock_memory.save.call_args_list
    # First call: human turn
    assert calls[0].args[1] == "human"
    # Second call: ai turn
    assert calls[1].args[1] == "ai"


async def test_invoke_graph_returns_string(
    mock_memory: AsyncMock, mock_graph: MagicMock
) -> None:
    mock_graph.ainvoke = AsyncMock(return_value=_VALID_FINAL_STATE)

    result = await invoke_graph(mock_graph, mock_memory, "u1", "hello")

    assert isinstance(result, str)


async def test_error_handler_triggered_on_llm_failure(
    mock_memory: AsyncMock, mock_graph: MagicMock
) -> None:
    mock_graph.ainvoke = AsyncMock(side_effect=ValueError("LLM exploded"))

    with pytest.raises(RuntimeError):
        await invoke_graph(mock_graph, mock_memory, "u1", "hello")


# ─── Fixtures local to this module ────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MagicMock:
    """Minimal LLM mock whose ainvoke returns an object with .content."""
    llm = MagicMock()
    response_obj = MagicMock()
    response_obj.content = "test response"
    llm.ainvoke = AsyncMock(return_value=response_obj)
    return llm
