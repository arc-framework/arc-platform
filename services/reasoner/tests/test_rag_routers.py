"""Integration tests for the RAG routers: files, vector_stores, embeddings.

Covers:
  - POST /v1/files (upload)
  - GET  /v1/files (list)
  - DELETE /v1/files/{id} (delete)
  - POST /v1/vector_stores (create)
  - POST /v1/vector_stores/{id}/files (attach async + sync)
  - GET  /v1/vector_stores/{id}/files/{fid} (file status)
  - POST /v1/vector_stores/{id}/search (search)
  - POST /v1/embeddings (get embeddings)
  - SHERLOCK_RAG_ENABLED=false -> all new routes return 503
  - usage.prompt_tokens non-zero in POST /v1/chat/completions
"""
from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sherlock.config import Settings
from sherlock.embeddings_router import router as embeddings_router
from sherlock.files_router import build_files_router
from sherlock.models_router import StaticModelRegistry
from sherlock.openai_router import build_openai_router
from sherlock.rag.store import RAGInfra
from sherlock.vector_stores_router import build_vector_stores_router

# ─── Default model used in chat completion tests ──────────────────────────────

_DEFAULT_MODEL = "mistralai/mistral-7b-instruct-v0.3"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_file_row(
    file_id: str = "file-abc123",
    filename: str = "test.txt",
    content_type: str = "text/plain",
    size: int = 11,
    status: str = "uploaded",
) -> MagicMock:
    """Build a mock DB row that the _file_object() helper can serialize."""
    row = MagicMock()
    row.id = file_id
    row.filename = filename
    row.content_type = content_type
    row.bytes = size
    row.minio_key = file_id
    row.status = status
    row.created_at = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    return row


def _make_vsf_row(
    vs_id: str = "vs-abc123",
    file_id: str = "file-abc123",
    status: str = "completed",
    chunk_count: int = 5,
) -> MagicMock:
    """Build a mock DB row for vector_store_files queries."""
    row = MagicMock()
    row.vector_store_id = vs_id
    row.file_id = file_id
    row.status = status
    row.chunk_count = chunk_count
    row.error_message = None
    return row


def _make_session(
    fetchone_return: Any = None,
    fetchall_return: list[Any] | None = None,
) -> AsyncMock:
    """Return a fully-wired async session mock supporting both context manager forms.

    Supports:
      async with _session_factory() as session:          (plain)
      async with _session_factory() as session, session.begin():  (chained begin)
    """
    result_mock = MagicMock()
    result_mock.fetchone = MagicMock(return_value=fetchone_return)
    result_mock.fetchall = MagicMock(return_value=fetchall_return or [])

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    # Support `async with session.begin():`
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=begin_ctx)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    # Support `async with _session_factory() as session:`
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _set_session_factory(mock_rag: MagicMock, session: AsyncMock) -> None:
    """Set _session_factory to always return the given session (sync side_effect)."""
    mock_rag.vector_store._session_factory.return_value = session
    mock_rag.vector_store._session_factory.side_effect = None


def _set_session_factory_sequence(
    mock_rag: MagicMock, sessions: list[AsyncMock]
) -> None:
    """Set _session_factory to return sessions in order (sync side_effect)."""
    call_iter = iter(sessions)

    def _factory_side_effect() -> AsyncMock:
        return next(call_iter)

    mock_rag.vector_store._session_factory.side_effect = _factory_side_effect


# ─── Mock RAGInfra fixture ────────────────────────────────────────────────────


@pytest.fixture
def mock_rag_infra() -> MagicMock:
    """Minimal RAGInfra mock with sensible defaults (no live services)."""
    mock_rag = MagicMock(spec=RAGInfra)

    # Settings defaults needed by routers
    mock_rag.settings = MagicMock()
    mock_rag.settings.max_file_bytes = 50 * 1024 * 1024
    mock_rag.settings.hybrid_alpha = 0.7
    mock_rag.settings.retrieval_top_k = 5
    mock_rag.settings.retrieval_candidate_k = 50
    mock_rag.settings.sync_timeout_s = 30.0

    # File store
    mock_rag.file_store = MagicMock()
    mock_rag.file_store.upload = AsyncMock()
    mock_rag.file_store.download = AsyncMock(return_value=b"hello world")
    mock_rag.file_store.delete = AsyncMock()
    mock_rag.file_store.health_check = AsyncMock(return_value={"minio": True})

    # Vector store — _session_factory is configured per-test below
    mock_rag.vector_store = MagicMock()
    mock_rag.vector_store.delete_by_file = AsyncMock()

    # Embedder
    mock_rag.embedder = MagicMock()
    mock_rag.embedder.encode = MagicMock(return_value=[[0.1, 0.2, 0.3]])

    # Retriever
    mock_rag.retriever = MagicMock()
    mock_rag.retriever.search = AsyncMock(return_value=[])

    # Ingest pipeline
    mock_rag.ingest_pipeline = MagicMock()
    mock_rag.ingest_pipeline.ingest = AsyncMock(return_value=5)

    return mock_rag


# ─── Test app factory ─────────────────────────────────────────────────────────


def _make_rag_app(app_state: Any) -> FastAPI:
    """Create a minimal FastAPI test app with all RAG routers mounted."""
    application = FastAPI()
    application.include_router(build_files_router(), prefix="/v1")
    application.include_router(build_vector_stores_router(), prefix="/v1")
    application.include_router(embeddings_router, prefix="/v1")
    application.state.app_state = app_state
    return application


# ─── Shared app_state fixture (with RAG) ─────────────────────────────────────


@pytest.fixture
def rag_app_state(mock_rag_infra: MagicMock) -> MagicMock:
    """AppState-like object with rag populated."""
    state = MagicMock()
    state.rag = mock_rag_infra
    return state


@pytest.fixture
def no_rag_app_state() -> MagicMock:
    """AppState-like object with rag=None (simulates disabled RAG)."""
    state = MagicMock()
    state.rag = None
    return state


# ─── Async clients ────────────────────────────────────────────────────────────


@pytest.fixture
async def rag_client(rag_app_state: MagicMock) -> Any:
    """httpx AsyncClient for RAG-enabled app."""
    app = _make_rag_app(rag_app_state)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def no_rag_client(no_rag_app_state: MagicMock) -> Any:
    """httpx AsyncClient for app with RAG disabled (rag=None)."""
    app = _make_rag_app(no_rag_app_state)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ═══════════════════════════════════════════════════════════════════════════════
# Files API Tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_upload_file_returns_201(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/files with a valid .txt file returns 201 with a file object."""
    inserted_row = _make_file_row(filename="hello.txt")

    # upload_file calls _session_factory twice:
    #   1st: INSERT with session.begin() chained
    #   2nd: SELECT to fetch the row back
    session_insert = _make_session(fetchone_return=None)
    session_select = _make_session(fetchone_return=inserted_row)
    _set_session_factory_sequence(mock_rag_infra, [session_insert, session_select])

    response = await rag_client.post(
        "/v1/files",
        files={"file": ("hello.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["object"] == "file"
    assert body["filename"] == "hello.txt"
    assert body["bytes"] == 11
    assert body["purpose"] == "assistants"
    assert body["status"] == "uploaded"


async def test_upload_file_unsupported_extension_returns_400(
    rag_client: Any,
) -> None:
    """POST /v1/files with an unsupported extension returns 400."""
    response = await rag_client.post(
        "/v1/files",
        files={"file": ("malware.exe", b"\x00\x01\x02", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["error"]


async def test_list_files_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """GET /v1/files returns 200 with data list."""
    rows = [_make_file_row("file-1", "a.txt"), _make_file_row("file-2", "b.md")]
    session = _make_session(fetchall_return=rows)
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.get("/v1/files")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert len(body["data"]) == 2
    assert body["data"][0]["filename"] == "a.txt"
    assert body["data"][1]["filename"] == "b.md"


async def test_list_files_empty(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """GET /v1/files with no files returns empty data list."""
    session = _make_session(fetchall_return=[])
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.get("/v1/files")

    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_delete_file_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """DELETE /v1/files/{id} returns 200 with deleted=True."""
    row = _make_file_row("file-del1")

    # delete_file calls _session_factory twice:
    #   1st: SELECT to verify existence
    #   2nd: DELETE with session.begin() chained
    session_select = _make_session(fetchone_return=row)
    session_delete = _make_session(fetchone_return=None)
    _set_session_factory_sequence(mock_rag_infra, [session_select, session_delete])

    response = await rag_client.delete("/v1/files/file-del1")

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] is True
    assert body["id"] == "file-del1"


async def test_delete_file_not_found_returns_404(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """DELETE /v1/files/{id} for a missing file returns 404."""
    session = _make_session(fetchone_return=None)
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.delete("/v1/files/file-missing")

    assert response.status_code == 404


# ─── RAG disabled: files routes return 503 ────────────────────────────────────


async def test_upload_file_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """POST /v1/files with RAG disabled returns 503."""
    response = await no_rag_client.post(
        "/v1/files",
        files={"file": ("test.txt", b"data", "text/plain")},
    )
    assert response.status_code == 503


async def test_list_files_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """GET /v1/files with RAG disabled returns 503."""
    response = await no_rag_client.get("/v1/files")
    assert response.status_code == 503


async def test_delete_file_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """DELETE /v1/files/{id} with RAG disabled returns 503."""
    response = await no_rag_client.delete("/v1/files/file-abc")
    assert response.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Vector Stores API Tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_create_vector_store_returns_201(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/vector_stores returns 201 with a vector_store object."""
    session = _make_session()
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.post(
        "/v1/vector_stores",
        json={"name": "my-knowledge-base"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["object"] == "vector_store"
    assert body["name"] == "my-knowledge-base"
    assert "id" in body
    assert body["id"].startswith("vs-")
    assert "created_at" in body


async def test_attach_file_async_returns_202(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/vector_stores/{id}/files (async default) returns 202 queued."""
    vsf_row = _make_vsf_row(status="queued")

    # attach_file calls _session_factory twice:
    #   1st: INSERT with session.begin() chained (idempotent upsert)
    #   2nd: SELECT to check current status
    session_insert = _make_session()
    session_select = _make_session(fetchone_return=vsf_row)
    _set_session_factory_sequence(mock_rag_infra, [session_insert, session_select])

    response = await rag_client.post(
        "/v1/vector_stores/vs-abc123/files",
        json={"file_id": "file-abc123"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["object"] == "vector_store.file"
    assert body["status"] == "queued"
    assert body["id"] == "file-abc123"


async def test_attach_file_sync_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/vector_stores/{id}/files?sync=true returns 200 completed."""
    vsf_row = _make_vsf_row(status="queued")

    session_insert = _make_session()
    session_select = _make_session(fetchone_return=vsf_row)
    _set_session_factory_sequence(mock_rag_infra, [session_insert, session_select])
    mock_rag_infra.ingest_pipeline.ingest = AsyncMock(return_value=5)

    response = await rag_client.post(
        "/v1/vector_stores/vs-abc123/files?sync=true",
        json={"file_id": "file-abc123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] == 5


async def test_attach_file_idempotent_already_completed(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """Attaching a file already in 'completed' status returns 200 with existing state."""
    vsf_row = _make_vsf_row(status="completed", chunk_count=10)

    session_insert = _make_session()
    session_select = _make_session(fetchone_return=vsf_row)
    _set_session_factory_sequence(mock_rag_infra, [session_insert, session_select])

    response = await rag_client.post(
        "/v1/vector_stores/vs-abc123/files",
        json={"file_id": "file-abc123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] == 10


async def test_get_file_status_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """GET /v1/vector_stores/{id}/files/{fid} returns 200 with file status."""
    vsf_row = _make_vsf_row(status="completed", chunk_count=7)
    session = _make_session(fetchone_return=vsf_row)
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.get("/v1/vector_stores/vs-abc123/files/file-abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "vector_store.file"
    assert body["status"] == "completed"
    assert body["chunk_count"] == 7
    assert body["id"] == "file-abc123"


async def test_get_file_status_not_found_returns_404(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """GET /v1/vector_stores/{id}/files/{fid} for missing file returns 404."""
    session = _make_session(fetchone_return=None)
    _set_session_factory(mock_rag_infra, session)

    response = await rag_client.get("/v1/vector_stores/vs-abc123/files/file-missing")

    assert response.status_code == 404


async def test_search_vector_store_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/vector_stores/{id}/search returns 200 with data list."""
    mock_rag_infra.retriever.search = AsyncMock(return_value=[])

    response = await rag_client.post(
        "/v1/vector_stores/vs-abc123/search",
        json={"query": "what is sherlock?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert isinstance(body["data"], list)


async def test_search_vector_store_with_results(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/vector_stores/{id}/search returns result chunks."""
    chunk = MagicMock()
    chunk.chunk_id = "chunk-1"
    chunk.content = "Sherlock solves mysteries"
    chunk.score = 0.95
    chunk.metadata = {"source": "test.txt"}
    mock_rag_infra.retriever.search = AsyncMock(return_value=[chunk])

    response = await rag_client.post(
        "/v1/vector_stores/vs-abc123/search",
        json={"query": "mystery solver", "top_k": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    result = body["data"][0]
    assert result["chunk_id"] == "chunk-1"
    assert result["content"] == "Sherlock solves mysteries"
    assert result["score"] == 0.95


# ─── RAG disabled: vector_stores routes return 503 ───────────────────────────


async def test_create_vector_store_rag_disabled_returns_503(
    no_rag_client: Any,
) -> None:
    """POST /v1/vector_stores with RAG disabled returns 503."""
    response = await no_rag_client.post(
        "/v1/vector_stores", json={"name": "should-fail"}
    )
    assert response.status_code == 503


async def test_attach_file_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """POST /v1/vector_stores/{id}/files with RAG disabled returns 503."""
    response = await no_rag_client.post(
        "/v1/vector_stores/vs-xyz/files",
        json={"file_id": "file-xyz"},
    )
    assert response.status_code == 503


async def test_get_file_status_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """GET /v1/vector_stores/{id}/files/{fid} with RAG disabled returns 503."""
    response = await no_rag_client.get("/v1/vector_stores/vs-xyz/files/file-xyz")
    assert response.status_code == 503


async def test_search_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """POST /v1/vector_stores/{id}/search with RAG disabled returns 503."""
    response = await no_rag_client.post(
        "/v1/vector_stores/vs-xyz/search",
        json={"query": "something"},
    )
    assert response.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Embeddings API Tests
# ═══════════════════════════════════════════════════════════════════════════════


async def test_embeddings_single_string_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/embeddings with a string input returns 200 with embedding data."""
    mock_rag_infra.embedder.encode = MagicMock(return_value=[[0.1, 0.2, 0.3]])

    response = await rag_client.post(
        "/v1/embeddings",
        json={"model": "text-embedding-ada-002", "input": "hello world"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert len(body["data"]) == 1
    assert body["data"][0]["object"] == "embedding"
    assert body["data"][0]["index"] == 0
    assert isinstance(body["data"][0]["embedding"], list)
    assert body["usage"]["prompt_tokens"] > 0
    assert body["usage"]["total_tokens"] > 0


async def test_embeddings_list_input_returns_200(
    rag_client: Any, mock_rag_infra: MagicMock
) -> None:
    """POST /v1/embeddings with a list input returns multiple embeddings."""
    mock_rag_infra.embedder.encode = MagicMock(
        return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    )

    response = await rag_client.post(
        "/v1/embeddings",
        json={"model": "text-embedding-ada-002", "input": ["foo", "bar"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["index"] == 0
    assert body["data"][1]["index"] == 1


async def test_embeddings_rag_disabled_returns_503(no_rag_client: Any) -> None:
    """POST /v1/embeddings with RAG disabled returns 503."""
    response = await no_rag_client.post(
        "/v1/embeddings",
        json={"model": "text-embedding-ada-002", "input": "test"},
    )
    assert response.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Chat Completions: usage.prompt_tokens must be non-zero (Task acceptance #10)
# ═══════════════════════════════════════════════════════════════════════════════


async def test_chat_completions_usage_prompt_tokens_nonzero() -> None:
    """POST /v1/chat/completions response must have non-zero usage.prompt_tokens."""
    settings = Settings()
    registry = StaticModelRegistry(settings)

    streaming_adapter = MagicMock()
    streaming_adapter.stream = MagicMock()

    metrics_mock = MagicMock()
    metrics_mock.v1_requests_total = MagicMock()
    metrics_mock.v1_requests_total.add = MagicMock()
    metrics_mock.v1_errors_total = MagicMock()
    metrics_mock.v1_errors_total.add = MagicMock()
    metrics_mock.v1_latency = MagicMock()
    metrics_mock.v1_latency.record = MagicMock()

    state = MagicMock()
    state.graph = MagicMock()
    state.memory = MagicMock()
    state.metrics = metrics_mock
    state.rag = None

    application = FastAPI()
    router = build_openai_router(registry, streaming_adapter)
    application.include_router(router, prefix="/v1")
    application.state.app_state = state

    with patch(
        "sherlock.openai_router.invoke_graph", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "hello"
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": _DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": "What is 2+2?"}],
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert "usage" in body
    assert body["usage"]["prompt_tokens"] > 0, (
        f"Expected prompt_tokens > 0, got: {body['usage']}"
    )
    assert body["usage"]["completion_tokens"] > 0
    assert body["usage"]["total_tokens"] == (
        body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
    )
