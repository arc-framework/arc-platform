"""Unit tests for sherlock.memory.SherlockMemory.

All tests run without live Qdrant or PostgreSQL — every external call is mocked.
asyncio_mode = "auto" is set in pyproject.toml so no explicit @pytest.mark.asyncio
decorator is needed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sherlock.config import Settings
from sherlock.memory import SherlockMemory


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    """Return a MagicMock Settings with just the attributes SherlockMemory reads."""
    s = MagicMock(spec=Settings)
    s.qdrant_host = "localhost"
    s.qdrant_port = 6333
    s.postgres_url = "postgresql+asyncpg://arc:arc@localhost:5432/arc"
    s.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    s.context_top_k = 5
    s.qdrant_collection = "sherlock_conversations"
    s.embedding_dim = 384
    return s


def _make_mock_engine() -> MagicMock:
    """Return a mock AsyncEngine whose begin() and connect() context managers work."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    @asynccontextmanager
    async def _begin():  # type: ignore[override]
        yield mock_conn

    @asynccontextmanager
    async def _connect():  # type: ignore[override]
        yield mock_conn

    engine = MagicMock()
    engine.begin = _begin
    engine.connect = _connect
    return engine, mock_conn


# ─── init() — Qdrant collection bootstrap ─────────────────────────────────────


async def test_init_creates_qdrant_collection() -> None:
    """When no collections exist, create_collection is called once."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_qdrant = AsyncMock()
    # get_collections returns object with empty .collections list
    collections_response = MagicMock()
    collections_response.collections = []
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)
    mock_qdrant.create_collection = AsyncMock()

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer"),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    mock_qdrant.create_collection.assert_called_once()
    call_kwargs = mock_qdrant.create_collection.call_args.kwargs
    assert call_kwargs["collection_name"] == "sherlock_conversations"


async def test_init_idempotent_existing_collection() -> None:
    """When the collection already exists, create_collection is NOT called."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_qdrant = AsyncMock()
    existing_col = MagicMock()
    existing_col.name = "sherlock_conversations"
    collections_response = MagicMock()
    collections_response.collections = [existing_col]
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)
    mock_qdrant.create_collection = AsyncMock()

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer"),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    mock_qdrant.create_collection.assert_not_called()


# ─── init() — PostgreSQL schema bootstrap ─────────────────────────────────────


async def test_init_creates_postgres_schema() -> None:
    """init() executes CREATE SCHEMA IF NOT EXISTS sherlock via the engine."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    mock_qdrant = AsyncMock()
    collections_response = MagicMock()
    collections_response.collections = []
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)
    mock_qdrant.create_collection = AsyncMock()

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer"),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    # conn.execute must have been called at least once with a CREATE SCHEMA statement
    assert mock_conn.execute.call_count >= 1
    executed_stmts = [str(call.args[0]) for call in mock_conn.execute.call_args_list]
    assert any("CREATE SCHEMA IF NOT EXISTS sherlock" in s for s in executed_stmts)


# ─── search() ─────────────────────────────────────────────────────────────────


async def test_search_returns_list_of_strings() -> None:
    """search() encodes the query, calls qdrant.search, and returns payload content."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_qdrant = AsyncMock()
    hit = MagicMock()
    hit.payload = {"content": "past message"}
    mock_qdrant.search = AsyncMock(return_value=[hit])

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer", return_value=mock_encoder),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.search("user1", "query")

    assert result == ["past message"]
    mock_qdrant.search.assert_called_once()


# ─── save() ───────────────────────────────────────────────────────────────────


async def test_save_upserts_qdrant_and_inserts_postgres() -> None:
    """save() calls qdrant.upsert and the async session add+commit."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_qdrant = AsyncMock()
    mock_qdrant.upsert = AsyncMock()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    # sessionmaker() returns a context manager that yields mock_session
    @asynccontextmanager
    async def _session_ctx():  # type: ignore[override]
        yield mock_session

    mock_session_factory = MagicMock(return_value=_session_ctx())

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer", return_value=mock_encoder),
        patch("sherlock.memory.sessionmaker", return_value=mock_session_factory),
    ):
        mem = SherlockMemory(settings)
        await mem.save("user1", "human", "hello")

    mock_qdrant.upsert.assert_called_once()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


# ─── health_check() ───────────────────────────────────────────────────────────


async def test_health_check_qdrant_down() -> None:
    """When qdrant.get_collections raises, qdrant is False; postgres probed independently."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    mock_qdrant = AsyncMock()
    mock_qdrant.get_collections = AsyncMock(side_effect=Exception("connection refused"))

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer"),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.health_check()

    assert result["qdrant"] is False
    assert result["postgres"] is True


async def test_health_check_both_healthy() -> None:
    """When both stores respond, health_check returns True for each."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    mock_qdrant = AsyncMock()
    collections_response = MagicMock()
    collections_response.collections = []
    mock_qdrant.get_collections = AsyncMock(return_value=collections_response)

    with (
        patch("sherlock.memory.AsyncQdrantClient", return_value=mock_qdrant),
        patch("sherlock.memory.create_async_engine", return_value=mock_engine),
        patch("sherlock.memory.SentenceTransformer"),
        patch("sherlock.memory.sessionmaker"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.health_check()

    assert result["qdrant"] is True
    assert result["postgres"] is True
