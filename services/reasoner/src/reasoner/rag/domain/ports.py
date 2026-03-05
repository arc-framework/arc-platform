"""RAG hexagonal architecture port interfaces.

Adapters in ``rag/adapters/`` implement these Protocols structurally (duck
typing — no inheritance required). Application services depend only on these
abstractions, never on concrete adapter types.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from reasoner.rag.domain.models import SearchResult

# ─── FileStorePort ────────────────────────────────────────────────────────────


@runtime_checkable
class FileStorePort(Protocol):
    """Object storage (MinIO) operations."""

    async def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    async def download(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def health_check(self) -> dict[str, bool]: ...


# ─── VectorStorePort ──────────────────────────────────────────────────────────


@runtime_checkable
class VectorStorePort(Protocol):
    """PostgreSQL + pgvector operations."""

    async def init_schema(self) -> None: ...

    async def upsert_chunks(
        self,
        vs_id: str,
        file_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int: ...

    async def search_hybrid(
        self,
        query_vec: list[float],
        query_text: str,
        vs_ids: list[str],
        alpha: float,
        candidate_k: int,
    ) -> list[SearchResult]: ...

    async def delete_by_file(self, file_id: str) -> None: ...

    async def delete_vs(self, vs_id: str) -> None: ...


# ─── EmbedderPort ─────────────────────────────────────────────────────────────


@runtime_checkable
class EmbedderPort(Protocol):
    """Sentence embedding."""

    def encode(self, texts: list[str]) -> list[list[float]]: ...


# ─── RerankerPort ─────────────────────────────────────────────────────────────


@runtime_checkable
class RerankerPort(Protocol):
    """Cross-encoder reranking."""

    async def rerank(self, query: str, texts: list[str]) -> list[float]: ...
