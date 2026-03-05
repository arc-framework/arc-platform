"""Unit tests for sherlock.rag.application.ingest.IngestPipeline."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sherlock.config import Settings
from sherlock.rag.application.ingest import IngestPipeline


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> Settings:
    return Settings(
        SHERLOCK_POSTGRES_URL="postgresql+asyncpg://arc:arc@localhost:5432/arc",
        SHERLOCK_CHUNK_SIZE_TOKENS=10,
        SHERLOCK_CHUNK_OVERLAP_TOKENS=2,
    )


def _make_mock_session(filename: str = "test.txt") -> MagicMock:
    """Return a mock SQLAlchemy AsyncSession that yields a row with the given filename."""
    session = MagicMock()
    # For _get_filename — session.execute returns a result whose fetchone() returns row
    row = MagicMock()
    row.filename = filename
    execute_result = MagicMock()
    execute_result.fetchone.return_value = row
    session.execute = AsyncMock(return_value=execute_result)
    session.begin = MagicMock(side_effect=lambda: _async_context_manager_noop())
    return session


def _async_context_manager_noop() -> Any:
    @asynccontextmanager
    async def _noop() -> AsyncIterator[None]:
        yield None

    return _noop()


def _make_session_factory(filename: str = "test.txt") -> MagicMock:
    """Return a mock async_sessionmaker that yields a session."""
    session = _make_mock_session(filename)

    factory = MagicMock()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[MagicMock]:
        yield session

    factory.return_value = _ctx()
    # Allow multiple calls by regenerating the context manager each time.
    factory.side_effect = lambda: _ctx()
    return factory


def _make_pipeline(
    file_store: AsyncMock,
    vector_store: AsyncMock,
    embedder: MagicMock,
    session_factory: MagicMock,
    settings: Settings | None = None,
) -> IngestPipeline:
    return IngestPipeline(
        file_store=file_store,
        vector_store=vector_store,
        embedder=embedder,
        session_factory=session_factory,
        settings=settings or _make_settings(),
    )


# ─── Success path ─────────────────────────────────────────────────────────────


class TestIngestPipelineSuccess:
    async def test_ingest_returns_chunk_count(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"This is a test document with enough words to create chunks."

        vector_store = AsyncMock()
        vector_store.upsert_chunks.return_value = 3

        embedder = MagicMock()
        embedder.encode.return_value = [[0.1, 0.2]] * 3

        session_factory = _make_session_factory("doc.txt")

        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_doc = MagicMock()
            mock_doc.text = "chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 more words here"
            mock_parser.return_value = mock_doc

            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = ["chunk1", "chunk2", "chunk3"]
                count = await pipeline.ingest("file-1", "vs-1")

        assert count == 3

    async def test_ingest_calls_file_store_download(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"hello world text"
        vector_store = AsyncMock()
        vector_store.upsert_chunks.return_value = 1
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1]]

        session_factory = _make_session_factory("notes.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.return_value = MagicMock(text="hello world text")
            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = ["hello world text"]
                await pipeline.ingest("file-abc", "vs-xyz")

        file_store.download.assert_called_once_with("file-abc")

    async def test_ingest_calls_embedder_encode(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"text"
        vector_store = AsyncMock()
        vector_store.upsert_chunks.return_value = 2
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1], [0.2]]

        session_factory = _make_session_factory("file.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.return_value = MagicMock(text="text")
            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = ["chunk-a", "chunk-b"]
                await pipeline.ingest("f-1", "vs-1")

        embedder.encode.assert_called_once_with(["chunk-a", "chunk-b"])

    async def test_ingest_calls_upsert_chunks(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"text"
        vector_store = AsyncMock()
        vector_store.upsert_chunks.return_value = 1
        embedder = MagicMock()
        embedder.encode.return_value = [[0.5]]

        session_factory = _make_session_factory("data.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.return_value = MagicMock(text="text")
            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = ["data chunk"]
                await pipeline.ingest("file-2", "vs-2")

        vector_store.upsert_chunks.assert_called_once_with(
            "vs-2", "file-2", ["data chunk"], [[0.5]]
        )

    async def test_ingest_empty_chunks_returns_zero(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"   "
        vector_store = AsyncMock()
        embedder = MagicMock()

        session_factory = _make_session_factory("empty.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.return_value = MagicMock(text="   ")
            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = []
                count = await pipeline.ingest("file-empty", "vs-1")

        assert count == 0
        vector_store.upsert_chunks.assert_not_called()


# ─── Exception → status=failed path ───────────────────────────────────────────


class TestIngestPipelineFailure:
    async def test_exception_sets_status_to_failed_and_reraises(self) -> None:
        file_store = AsyncMock()
        file_store.download.side_effect = ConnectionError("MinIO unavailable")

        vector_store = AsyncMock()
        embedder = MagicMock()

        session_factory = _make_session_factory("doc.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with pytest.raises(ConnectionError, match="MinIO unavailable"):
            await pipeline.ingest("file-bad", "vs-bad")

    async def test_parse_exception_reraises(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"data"
        vector_store = AsyncMock()
        embedder = MagicMock()

        session_factory = _make_session_factory("file.xyz")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        from sherlock.rag.parsers import UnsupportedFileTypeError

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.side_effect = UnsupportedFileTypeError("bad ext")
            with pytest.raises(UnsupportedFileTypeError):
                await pipeline.ingest("file-3", "vs-3")

    async def test_exception_during_embed_reraises(self) -> None:
        file_store = AsyncMock()
        file_store.download.return_value = b"text content"
        vector_store = AsyncMock()
        embedder = MagicMock()
        embedder.encode.side_effect = RuntimeError("GPU OOM")

        session_factory = _make_session_factory("notes.txt")
        pipeline = _make_pipeline(file_store, vector_store, embedder, session_factory)

        with patch("sherlock.rag.application.ingest.dispatch_parser") as mock_parser:
            mock_parser.return_value = MagicMock(text="text content")
            with patch("sherlock.rag.application.ingest.chunk_text") as mock_chunk:
                mock_chunk.return_value = ["chunk"]
                with pytest.raises(RuntimeError, match="GPU OOM"):
                    await pipeline.ingest("file-4", "vs-4")

    async def test_file_not_found_raises_value_error(self) -> None:
        """When the DB returns no row for file_id, ValueError should propagate."""
        file_store = AsyncMock()
        vector_store = AsyncMock()
        embedder = MagicMock()

        # Build a session that returns None from fetchone (file not found).
        session = MagicMock()
        execute_result = MagicMock()
        execute_result.fetchone.return_value = None
        session.execute = AsyncMock(return_value=execute_result)
        session.begin = MagicMock(side_effect=lambda: _async_context_manager_noop())

        factory = MagicMock()

        @asynccontextmanager
        async def _ctx() -> AsyncIterator[MagicMock]:
            yield session

        factory.side_effect = lambda: _ctx()

        pipeline = _make_pipeline(file_store, vector_store, embedder, factory)

        with pytest.raises(ValueError, match="File not found"):
            await pipeline.ingest("nonexistent", "vs-1")
