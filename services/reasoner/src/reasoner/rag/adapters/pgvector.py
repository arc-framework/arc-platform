"""PostgreSQL + pgvector vector store adapter.

Implements ``VectorStorePort`` using SQLAlchemy async sessions backed by asyncpg.
Schema DDL lives in services/persistence/initdb/004_reasoner_rag_schema.sql and
is applied at DB startup — ``init_schema`` only verifies accessibility.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from pgvector.asyncpg import register_vector
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from reasoner.rag.domain.models import SearchResult

_log = structlog.get_logger(__name__)

# ─── Hybrid search SQL ────────────────────────────────────────────────────────

_HYBRID_SQL = """\
WITH dense AS (
    SELECT id,
           file_id,
           vector_store_id,
           content,
           chunk_index,
           1 - (embedding <=> :query_vec::vector) AS dense_score
    FROM reasoner.knowledge_chunks
    WHERE vector_store_id = ANY(:vs_ids)
      AND embedding IS NOT NULL
),
fts AS (
    SELECT id,
           ts_rank(fts_vector, plainto_tsquery('english', :query_text)) AS fts_score
    FROM reasoner.knowledge_chunks
    WHERE vector_store_id = ANY(:vs_ids)
      AND fts_vector @@ plainto_tsquery('english', :query_text)
),
combined AS (
    SELECT d.id,
           d.file_id,
           d.vector_store_id,
           d.content,
           d.chunk_index,
           :alpha * d.dense_score + (1 - :alpha) * COALESCE(f.fts_score, 0) AS score
    FROM dense d
    LEFT JOIN fts f ON d.id = f.id
)
SELECT id, file_id, vector_store_id, content, chunk_index, score
FROM combined
ORDER BY score DESC
LIMIT :candidate_k
"""

_INSERT_CHUNK_SQL = """\
INSERT INTO reasoner.knowledge_chunks
    (id, vector_store_id, file_id, chunk_index, content, embedding)
VALUES
    (:id, :vector_store_id, :file_id, :chunk_index, :content, :embedding::vector)
ON CONFLICT (id) DO UPDATE
    SET content   = EXCLUDED.content,
        embedding = EXCLUDED.embedding
"""

_DELETE_BY_FILE_SQL = "DELETE FROM reasoner.knowledge_chunks WHERE file_id = :file_id"

_DELETE_BY_VS_SQL = (
    "DELETE FROM reasoner.knowledge_chunks WHERE vector_store_id = :vector_store_id"
)

_CHECK_SCHEMA_SQL = "SELECT 1 FROM reasoner.knowledge_chunks LIMIT 0"


# ─── PgVectorStore ────────────────────────────────────────────────────────────


class PgVectorStore:
    """VectorStorePort implementation backed by PostgreSQL + pgvector."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        # asyncpg requires the vector codec registered per connection.
        def _on_connect(dbapi_conn: Any, _: Any) -> None:
            dbapi_conn.run_async(register_vector)

        event.listen(engine.sync_engine, "connect", _on_connect)

    # ─── VectorStorePort interface ─────────────────────────────────────────────

    async def init_schema(self) -> None:
        """Verify the RAG schema is accessible (idempotent).

        The DDL is applied by services/persistence/initdb/004_reasoner_rag_schema.sql
        at DB startup. This method simply checks connectivity; it logs an error
        but does not raise so the service can start in degraded mode.
        """
        try:
            async with self._session_factory() as session:
                await session.execute(text(_CHECK_SCHEMA_SQL))
            _log.debug("pgvector.init_schema.ok")
        except Exception:
            _log.error("pgvector.init_schema.failed", exc_info=True)

    async def upsert_chunks(
        self,
        vs_id: str,
        file_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        """Insert or update chunks with their embeddings.

        Returns the number of chunks written.
        """
        if not chunks:
            return 0

        rows = [
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{vs_id}:{file_id}:{i}")),
                "vector_store_id": vs_id,
                "file_id": file_id,
                "chunk_index": i,
                "content": content,
                "embedding": embedding,
            }
            for i, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True))
        ]

        async with self._session_factory() as session, session.begin():
            for row in rows:
                await session.execute(text(_INSERT_CHUNK_SQL), row)

        _log.debug("pgvector.upsert_chunks", vs_id=vs_id, file_id=file_id, count=len(rows))
        return len(rows)

    async def search_hybrid(
        self,
        query_vec: list[float],
        query_text: str,
        vs_ids: list[str],
        alpha: float,
        candidate_k: int,
    ) -> list[SearchResult]:
        """Execute alpha-weighted dense + FTS hybrid search.

        ``alpha=1.0`` is dense-only; ``alpha=0.0`` is FTS-only.
        """
        params: dict[str, Any] = {
            "query_vec": query_vec,
            "query_text": query_text,
            "vs_ids": vs_ids,
            "alpha": alpha,
            "candidate_k": candidate_k,
        }

        async with self._session_factory() as session:
            result = await session.execute(text(_HYBRID_SQL), params)
            rows = result.fetchall()

        return [
            SearchResult(
                chunk_id=str(row.id),
                file_id=str(row.file_id),
                vector_store_id=str(row.vector_store_id),
                content=row.content,
                score=float(row.score),
                chunk_index=row.chunk_index,
                metadata={
                    "file_id": str(row.file_id),
                    "vector_store_id": str(row.vector_store_id),
                    "chunk_index": row.chunk_index,
                },
            )
            for row in rows
        ]

    async def delete_by_file(self, file_id: str) -> None:
        """Delete all chunks belonging to *file_id*."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                text(_DELETE_BY_FILE_SQL), {"file_id": file_id}
            )
        _log.debug("pgvector.delete_by_file", file_id=file_id)

    async def delete_vs(self, vs_id: str) -> None:
        """Delete all chunks belonging to *vs_id*."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                text(_DELETE_BY_VS_SQL), {"vector_store_id": vs_id}
            )
        _log.debug("pgvector.delete_vs", vs_id=vs_id)
