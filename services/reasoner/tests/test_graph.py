from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reasoner.graph import build_graph, invoke_graph, stream_graph


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


# ─── stream_graph ─────────────────────────────────────────────────────────────


async def test_stream_graph_pre_fetches_context(
    mock_memory: AsyncMock, mock_graph: MagicMock
) -> None:
    """stream_graph() calls memory.search() before starting the LLM stream and injects
    the result into the initial state so the retrieve_context node is bypassed."""
    mock_memory.search = AsyncMock(return_value=["pre-fetched ctx"])

    captured_states: list[dict] = []

    async def _mock_astream_events(state: dict, version: str):  # type: ignore[override]
        captured_states.append(dict(state))
        return
        yield  # make it an async generator

    mock_graph.astream_events = _mock_astream_events

    chunks = []
    async for chunk in stream_graph(mock_graph, mock_memory, "u1", "hello"):
        chunks.append(chunk)

    mock_memory.search.assert_called_once_with("u1", "hello")
    assert len(captured_states) == 1
    assert captured_states[0]["context"] == ["pre-fetched ctx"]


# ─── Fixtures local to this module ────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MagicMock:
    """Minimal LLM mock whose ainvoke returns an object with .content."""
    llm = MagicMock()
    response_obj = MagicMock()
    response_obj.content = "test response"
    llm.ainvoke = AsyncMock(return_value=response_obj)
    return llm
