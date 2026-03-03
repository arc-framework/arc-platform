"""Tests for the OpenAI-compatible router: /v1/chat/completions and /v1/responses."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sherlock.config import Settings
from sherlock.models_router import StaticModelRegistry
from sherlock.models_v1 import ChatCompletionChunk, ChoiceDelta, StreamChoice
from sherlock.openai_router import build_openai_router

# ─── Helpers / constants ──────────────────────────────────────────────────────

_DEFAULT_MODEL = "mistralai/mistral-7b-instruct-v0.3"


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def registry(settings: Settings) -> StaticModelRegistry:
    return StaticModelRegistry(settings)


@pytest.fixture
def mock_streaming_adapter() -> MagicMock:
    """StreamingPort mock that yields two content chunks then a stop chunk."""
    adapter = MagicMock()

    async def _fake_stream(req: Any) -> Any:  # type: ignore[misc]
        chunk_id = "chatcmpl-test"
        created = 1700000000
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=req.model,
            choices=[StreamChoice(delta=ChoiceDelta(content="Hello"), finish_reason=None)],
        )
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=req.model,
            choices=[StreamChoice(delta=ChoiceDelta(content=" world"), finish_reason=None)],
        )
        # Final stop chunk
        yield ChatCompletionChunk(
            id=chunk_id,
            created=created,
            model=req.model,
            choices=[StreamChoice(delta=ChoiceDelta(content=None), finish_reason="stop")],
        )

    adapter.stream = _fake_stream
    return adapter


@pytest.fixture
def mock_metrics() -> MagicMock:
    """Minimal SherlockMetrics mock with no-op v1 instruments."""
    m = MagicMock()
    m.v1_requests_total = MagicMock()
    m.v1_requests_total.add = MagicMock()
    m.v1_errors_total = MagicMock()
    m.v1_errors_total.add = MagicMock()
    m.v1_latency = MagicMock()
    m.v1_latency.record = MagicMock()
    m.v1_stream_chunks = MagicMock()
    m.v1_stream_chunks.add = MagicMock()
    return m


@pytest.fixture
def fake_app_state(mock_metrics: MagicMock) -> MagicMock:
    """Minimal AppState-like object required by the router."""
    state = MagicMock()
    state.graph = MagicMock()
    state.memory = MagicMock()
    state.metrics = mock_metrics
    return state


@pytest.fixture
def test_app(
    registry: StaticModelRegistry,
    mock_streaming_adapter: MagicMock,
    fake_app_state: MagicMock,
) -> FastAPI:
    """Minimal FastAPI app that mounts the openai_router with AppState injected."""
    app = FastAPI()
    router = build_openai_router(registry, mock_streaming_adapter)
    app.include_router(router, prefix="/v1")
    app.state.app_state = fake_app_state
    return app


@pytest.fixture
def no_state_app(
    registry: StaticModelRegistry,
    mock_streaming_adapter: MagicMock,
) -> FastAPI:
    """FastAPI app WITHOUT app_state set — simulates service not ready."""
    app = FastAPI()
    router = build_openai_router(registry, mock_streaming_adapter)
    app.include_router(router, prefix="/v1")
    # Deliberately do NOT set app.state.app_state
    return app


@pytest.fixture
async def client(test_app: FastAPI) -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def no_state_client(no_state_app: FastAPI) -> Any:
    async with AsyncClient(
        transport=ASGITransport(app=no_state_app), base_url="http://test"
    ) as c:
        yield c


# ─── Acceptance Criterion 1: valid body → 200 ChatCompletionResponse ──────────


async def test_chat_completions_happy_path(client: Any) -> None:
    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "The answer is 42."
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": _DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "What is the answer?"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == _DEFAULT_MODEL
    assert len(body["choices"]) == 1
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "The answer is 42."
    assert "usage" in body
    assert "id" in body


# ─── Acceptance Criterion 2: stream=true → 200 text/event-stream with data: chunks ─


async def test_chat_completions_streaming(client: Any) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": _DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "Stream me something"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/event-stream" in content_type

    raw = response.text
    # At least one data: line must be present
    data_lines = [ln for ln in raw.splitlines() if ln.startswith("data:")]
    assert len(data_lines) >= 1, f"No 'data:' lines found in SSE response: {raw!r}"
    # The stream must terminate with data: [DONE]
    assert any(ln.strip() == "data: [DONE]" for ln in data_lines), (
        f"Missing 'data: [DONE]' sentinel in: {data_lines}"
    )


# ─── Acceptance Criterion 3: missing model → 404 model_not_found ─────────────


async def test_chat_completions_unknown_model(client: Any) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "unknown-model-xyz",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "model_not_found"
    assert body["error"]["type"] == "invalid_request_error"


async def test_responses_unknown_model(client: Any) -> None:
    response = await client.post(
        "/v1/responses",
        json={
            "model": "unknown-model-xyz",
            "input": "hello",
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "model_not_found"


# ─── Acceptance Criterion 4: no AppState → 503 ───────────────────────────────


async def test_chat_completions_no_app_state(no_state_client: Any) -> None:
    response = await no_state_client.post(
        "/v1/chat/completions",
        json={
            "model": _DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert "not ready" in body["detail"].lower()


async def test_responses_no_app_state(no_state_client: Any) -> None:
    response = await no_state_client.post(
        "/v1/responses",
        json={
            "model": _DEFAULT_MODEL,
            "input": "hello",
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert "not ready" in body["detail"].lower()


# ─── Acceptance Criterion 5: absent user field → valid result (no crash) ──────


async def test_chat_completions_absent_user_field(client: Any) -> None:
    """Router must derive user_id internally when user is not supplied."""
    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "reply without user field"
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": _DEFAULT_MODEL,
                # Deliberately omit 'user'
                "messages": [{"role": "user", "content": "anonymous question"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "reply without user field"
    # invoke_graph must have been called with a non-empty user_id derived internally
    mock_invoke.assert_called_once()
    called_user_id = mock_invoke.call_args[0][2]  # positional: graph, memory, user_id, text
    assert called_user_id, "user_id derived from messages must be non-empty"


# ─── Acceptance Criterion 6: POST /v1/responses with string input → 200 ──────


async def test_responses_string_input(client: Any) -> None:
    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "Sherlock deduces the truth."
        response = await client.post(
            "/v1/responses",
            json={
                "model": _DEFAULT_MODEL,
                "input": "What do you deduce?",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["model"] == _DEFAULT_MODEL
    assert body["status"] == "completed"
    assert len(body["output"]) == 1
    output_item = body["output"][0]
    assert output_item["type"] == "message"
    assert output_item["role"] == "assistant"
    assert len(output_item["content"]) == 1
    assert output_item["content"][0]["text"] == "Sherlock deduces the truth."
    assert "usage" in body


async def test_responses_list_input(client: Any) -> None:
    """POST /v1/responses also accepts a list of ResponseInputItem objects."""
    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "list-input reply"
        response = await client.post(
            "/v1/responses",
            json={
                "model": _DEFAULT_MODEL,
                "input": [{"role": "user", "content": "multi-turn question"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["output"][0]["content"][0]["text"] == "list-input reply"


# ─── Acceptance Criterion 7: no message content in log output ─────────────────


async def test_chat_completions_logs_no_message_content(client: Any) -> None:
    """Verify that structlog is never called with message content as a kwarg."""
    log_calls: list[dict[str, Any]] = []

    class _CapturingLogger:
        def debug(self, event: str, **kw: Any) -> None:
            log_calls.append({"event": event, "kwargs": kw})

        def error(self, event: str, **kw: Any) -> None:
            log_calls.append({"event": event, "kwargs": kw})

        def info(self, event: str, **kw: Any) -> None:
            log_calls.append({"event": event, "kwargs": kw})

        def warning(self, event: str, **kw: Any) -> None:
            log_calls.append({"event": event, "kwargs": kw})

    with (
        patch("sherlock.openai_router._log", _CapturingLogger()),
        patch("sherlock.openai_router.invoke_graph", new_callable=AsyncMock) as mock_invoke,
    ):
        mock_invoke.return_value = "response text"
        await client.post(
            "/v1/chat/completions",
            json={
                "model": _DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "super secret message"}],
            },
        )

    for entry in log_calls:
        kwargs = entry["kwargs"]
        # 'messages' key must not be present in any log call
        assert "messages" not in kwargs, (
            f"Log call contains 'messages' key: {entry}"
        )
        # The literal message content must not appear in logged values
        for val in kwargs.values():
            assert "super secret message" not in str(val), (
                f"Message content leaked in log: {entry}"
            )


# ─── Edge cases ───────────────────────────────────────────────────────────────


async def test_chat_completions_metrics_emitted(
    client: Any, fake_app_state: MagicMock
) -> None:
    """Metrics counter must be incremented on each request."""
    with patch("sherlock.openai_router.invoke_graph", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "ok"
        await client.post(
            "/v1/chat/completions",
            json={
                "model": _DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )

    fake_app_state.metrics.v1_requests_total.add.assert_called_once()


async def test_responses_instructions_echoed(client: Any) -> None:
    """instructions field from request is preserved in the response."""
    with patch("sherlock.openai_router.invoke_graph", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "following instructions"
        response = await client.post(
            "/v1/responses",
            json={
                "model": _DEFAULT_MODEL,
                "input": "do something",
                "instructions": "Be concise.",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["instructions"] == "Be concise."


async def test_chat_completions_explicit_user_passed_through(client: Any) -> None:
    """When user is explicitly set, it should be passed to invoke_graph as-is."""
    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "hi user-123"
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": _DEFAULT_MODEL,
                "messages": [{"role": "user", "content": "hello"}],
                "user": "user-123",
            },
        )

    assert response.status_code == 200
    mock_invoke.assert_called_once()
    called_user_id = mock_invoke.call_args[0][2]
    assert called_user_id == "user-123"
