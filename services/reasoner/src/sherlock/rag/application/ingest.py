"""IngestPipeline — orchestrates the full RAG ingestion flow."""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sherlock.config import Settings
from sherlock.rag.chunker import chunk_text
from sherlock.rag.domain.ports import EmbedderPort, FileStorePort, VectorStorePort
from sherlock.rag.parsers import dispatch_parser

_log = structlog.get_logger(__name__)


class IngestPipeline:
    """Orchestrates the full RAG ingestion flow: download → parse → chunk → embed → store."""

    def __init__(
        self,
        file_store: FileStorePort,
        vector_store: VectorStorePort,
        embedder: EmbedderPort,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._file_store = file_store
        self._vector_store = vector_store
        self._embedder = embedder
        self._session_factory = session_factory
        self._settings = settings

    async def ingest(self, file_id: str, vs_id: str) -> int:
        """Download, parse, chunk, embed, and store a file's chunks.

        Returns:
            Number of chunks ingested.

        Raises:
            Exception: Re-raised after updating vector_store_files status to 'failed'.
        """
        try:
            await self._update_status(file_id, vs_id, "processing", 0, None)

            filename = await self._get_filename(file_id)

            data = await self._file_store.download(file_id)

            doc = dispatch_parser(filename, data)

            chunks = chunk_text(
                doc.text,
                self._settings.chunk_size_tokens,
                self._settings.chunk_overlap_tokens,
            )

            if not chunks:
                await self._update_status(file_id, vs_id, "completed", 0, None)
                return 0

            embeddings = self._embedder.encode(chunks)

            chunk_count = await self._vector_store.upsert_chunks(vs_id, file_id, chunks, embeddings)

            await self._update_status(file_id, vs_id, "completed", chunk_count, None)

            _log.info("rag.ingest.completed", file_id=file_id, vs_id=vs_id, chunks=chunk_count)
            return chunk_count

        except Exception as exc:
            await self._update_status(file_id, vs_id, "failed", 0, str(exc))
            _log.error("rag.ingest.failed", file_id=file_id, vs_id=vs_id, error=str(exc))
            raise

    async def _get_filename(self, file_id: str) -> str:
        async with self._session_factory() as session:
            result = await session.execute(
                text("SELECT filename FROM sherlock.knowledge_files WHERE id = :file_id"),
                {"file_id": file_id},
            )
            row = result.fetchone()
            if row is None:
                raise ValueError(f"File not found: {file_id!r}")
            return str(row.filename)

    async def _update_status(
        self,
        file_id: str,
        vs_id: str,
        status: str,
        chunk_count: int,
        error_message: str | None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
                await session.execute(
                    text(
                        """
                        UPDATE sherlock.vector_store_files
                        SET status = :status,
                            chunk_count = :chunk_count,
                            error_message = :error_message
                        WHERE vector_store_id = :vs_id AND file_id = :file_id
                        """
                    ),
                    {
                        "status": status,
                        "chunk_count": chunk_count,
                        "error_message": error_message,
                        "vs_id": vs_id,
                        "file_id": file_id,
                    },
                )
