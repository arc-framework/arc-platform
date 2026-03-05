from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from reasoner.graph import stream_graph
from reasoner.models_v1 import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatMessage,
)
from reasoner.streaming import GraphStreamingAdapter, _derive_user_id

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_chunk(content: str) -> MagicMock:
    chunk = MagicMock()
    chunk.content = content
    return chunk


def _make_event(event_type: str, content: str | None = None) -> dict[str, Any]:
    if event_type == "on_chat_model_stream":
        return {"event": event_type, "data": {"chunk": _make_chunk(content or "")}}
    return {"event": event_type, "data": {}}


async def _collect(gen: AsyncGenerator[Any]) -> list[Any]:
    return [x async for x in gen]


# ─── stream_graph: token filtering ────────────────────────────────────────────


async def test_stream_graph_yields_tokens_from_chat_model_stream(
    mock_memory: AsyncMock,
) -> None:
    """Only on_chat_model_stream events yield tokens."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chain_start")
        yield _make_event("on_chat_model_stream", "Hello")
        yield _make_event("on_chat_model_stream", " world")

    mock_graph.astream_events = fake_events

    tokens = await _collect(stream_graph(mock_graph, mock_memory, "user1", "hello"))

    assert tokens == ["Hello", " world"]


async def test_stream_graph_skips_non_streaming_events(
    mock_memory: AsyncMock,
) -> None:
    """Events that are not on_chat_model_stream are silently skipped."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chain_start")
        yield _make_event("on_chain_end")
        yield _make_event("on_llm_start")
        yield _make_event("on_llm_end")

    mock_graph.astream_events = fake_events

    tokens = await _collect(stream_graph(mock_graph, mock_memory, "user1", "hi"))

    assert tokens == []


async def test_stream_graph_skips_empty_chunk_content(
    mock_memory: AsyncMock,
) -> None:
    """on_chat_model_stream events with empty content string are not yielded."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "")
        yield _make_event("on_chat_model_stream", "token")
        yield _make_event("on_chat_model_stream", "")

    mock_graph.astream_events = fake_events

    tokens = await _collect(stream_graph(mock_graph, mock_memory, "user1", "hi"))

    assert tokens == ["token"]


async def test_stream_graph_skips_none_chunk_content(
    mock_memory: AsyncMock,
) -> None:
    """Chunks whose .content is falsy (None or empty) are not yielded."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        chunk_none = MagicMock()
        chunk_none.content = None
        yield {"event": "on_chat_model_stream", "data": {"chunk": chunk_none}}
        yield _make_event("on_chat_model_stream", "real")

    mock_graph.astream_events = fake_events

    tokens = await _collect(stream_graph(mock_graph, mock_memory, "user1", "hi"))

    assert tokens == ["real"]


# ─── stream_graph: memory persistence ─────────────────────────────────────────


async def test_stream_graph_saves_both_turns_after_stream(
    mock_memory: AsyncMock,
) -> None:
    """memory.save() is called twice — once for human, once for AI — after stream ends."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "Hi")

    mock_graph.astream_events = fake_events

    await _collect(stream_graph(mock_graph, mock_memory, "user1", "hello"))

    assert mock_memory.save.await_count == 2
    calls = mock_memory.save.await_args_list
    assert calls[0].args[1] == "human"
    assert calls[1].args[1] == "ai"


async def test_stream_graph_saves_full_accumulated_response(
    mock_memory: AsyncMock,
) -> None:
    """The AI turn saved to memory is the full concatenated token stream."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "Foo")
        yield _make_event("on_chat_model_stream", " bar")

    mock_graph.astream_events = fake_events

    await _collect(stream_graph(mock_graph, mock_memory, "user1", "query"))

    calls = mock_memory.save.await_args_list
    ai_saved = calls[1].args[2]
    assert ai_saved == "Foo bar"


async def test_stream_graph_saves_fallback_when_no_tokens(
    mock_memory: AsyncMock,
) -> None:
    """When no tokens are yielded, memory saves the fallback string."""
    mock_graph = MagicMock()

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        # Yield nothing that matches the filter
        yield _make_event("on_chain_end")

    mock_graph.astream_events = fake_events

    await _collect(stream_graph(mock_graph, mock_memory, "user1", "query"))

    calls = mock_memory.save.await_args_list
    ai_saved = calls[1].args[2]
    assert ai_saved == "No response generated."


async def test_stream_graph_memory_failure_does_not_raise(
    mock_memory: AsyncMock,
) -> None:
    """Best-effort memory persistence — an exception from save() is swallowed."""
    mock_graph = MagicMock()
    mock_memory.save.side_effect = RuntimeError("storage down")

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "token")

    mock_graph.astream_events = fake_events

    # Must not raise even though memory.save() throws
    tokens = await _collect(stream_graph(mock_graph, mock_memory, "user1", "hi"))
    assert tokens == ["token"]


# ─── GraphStreamingAdapter: stream() return type ───────────────────────────────


def test_adapter_stream_returns_async_iterator(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """stream() is a sync method that returns an AsyncIterator, not a coroutine."""
    import inspect

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        return
        yield  # make it a generator

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test-model",
        messages=[ChatMessage(role="user", content="hello")],
    )

    result = adapter.stream(req)

    # stream() must NOT be a coroutine — it must be directly iterable
    assert not inspect.iscoroutine(result)
    assert hasattr(result, "__aiter__")


# ─── GraphStreamingAdapter: chunk fields ──────────────────────────────────────


async def test_adapter_chunks_have_correct_object_field(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Every yielded chunk carries object='chat.completion.chunk'."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="gpt-4",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    # All except the final finish chunk should have content
    assert all(c.object == "chat.completion.chunk" for c in chunks)


async def test_adapter_chunks_carry_model_from_request(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Chunks echo the model field from the request."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="claude-opus-4-6",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    assert all(c.model == "claude-opus-4-6" for c in chunks)


async def test_adapter_chunks_have_consistent_id(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """All chunks within a single stream share the same id."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok1")
        yield _make_event("on_chat_model_stream", "tok2")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    ids = {c.id for c in chunks}
    assert len(ids) == 1
    assert list(ids)[0].startswith("chatcmpl-")


async def test_adapter_token_chunks_have_delta_content(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Non-final chunks carry delta.content matching the yielded token."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "hello")
        yield _make_event("on_chat_model_stream", " there")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    # Last chunk is the finish chunk; all others carry token content
    token_chunks = chunks[:-1]
    assert [c.choices[0].delta.content for c in token_chunks] == ["hello", " there"]


# ─── GraphStreamingAdapter: final chunk ───────────────────────────────────────


async def test_adapter_final_chunk_has_finish_reason_stop(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """The last chunk always has finish_reason='stop'."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    final = chunks[-1]
    assert final.choices[0].finish_reason == "stop"


async def test_adapter_final_chunk_has_none_delta_content(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """The final chunk has delta.content=None to signal end of stream."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    final = chunks[-1]
    assert final.choices[0].delta.content is None


async def test_adapter_yields_finish_chunk_even_when_no_tokens(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Even with zero token events, exactly one finish chunk is emitted."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chain_start")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    assert len(chunks) == 1
    assert chunks[0].choices[0].finish_reason == "stop"


# ─── GraphStreamingAdapter: user_id derivation ────────────────────────────────


async def test_adapter_uses_req_user_when_set(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """When req.user is provided, it is passed as user_id to stream_graph."""
    captured_user_ids: list[str] = []

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        captured_user_ids.append(state["user_id"])
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
        user="explicit-user-id",
    )

    await _collect(adapter.stream(req))

    assert captured_user_ids == ["explicit-user-id"]


async def test_adapter_derives_user_id_via_uuid5_when_req_user_is_none(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """When req.user is None, user_id is a UUID v5 derived from message content."""
    captured_user_ids: list[str] = []

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        captured_user_ids.append(state["user_id"])
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    messages = [ChatMessage(role="user", content="hello world")]
    req = ChatCompletionRequest(
        model="test",
        messages=messages,
        user=None,
    )

    await _collect(adapter.stream(req))

    derived = captured_user_ids[0]
    # Must be a valid UUID
    parsed = uuid.UUID(derived)
    assert parsed.version == 5


async def test_adapter_derived_user_id_is_stable(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Same message content always produces the same derived user_id."""
    content = "deterministic input"
    expected = _derive_user_id([ChatMessage(role="user", content=content)])

    captured: list[str] = []

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        captured.append(state["user_id"])
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content=content)],
        user=None,
    )

    await _collect(adapter.stream(req))
    await _collect(adapter.stream(req))

    assert captured[0] == expected
    assert captured[0] == captured[1]


# ─── GraphStreamingAdapter: chunk type ────────────────────────────────────────


async def test_adapter_stream_yields_chat_completion_chunk_instances(
    mock_memory: AsyncMock,
    mock_graph: MagicMock,
) -> None:
    """Every item yielded by stream() is a ChatCompletionChunk."""

    async def fake_events(state: Any, version: str) -> AsyncGenerator[dict[str, Any]]:
        yield _make_event("on_chat_model_stream", "tok")

    mock_graph.astream_events = fake_events

    adapter = GraphStreamingAdapter(mock_graph, mock_memory)
    req = ChatCompletionRequest(
        model="test",
        messages=[ChatMessage(role="user", content="hi")],
    )

    chunks = await _collect(adapter.stream(req))

    assert all(isinstance(c, ChatCompletionChunk) for c in chunks)
