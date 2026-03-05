"""HybridRetriever — orchestrates hybrid search: embed → pgvector search → cross-encoder rerank."""
from __future__ import annotations

import structlog

from reasoner.rag.domain.models import SearchResult
from reasoner.rag.domain.ports import EmbedderPort, RerankerPort, VectorStorePort

_log = structlog.get_logger(__name__)


class HybridRetriever:
    """Orchestrates hybrid search: embed → pgvector search → cross-encoder rerank."""

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbedderPort,
        reranker: RerankerPort,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._reranker = reranker

    async def search(
        self,
        query: str,
        vs_ids: list[str],
        alpha: float,
        candidate_k: int,
        top_k: int,
    ) -> list[SearchResult]:
        """Run hybrid search and rerank to top_k results.

        Non-existent vs_ids produce empty results (pgvector adapter handles this gracefully).
        """
        if not vs_ids or not query.strip():
            return []

        # 1. Embed query (sync, CPU-bound)
        query_vecs = self._embedder.encode([query])
        query_vec = query_vecs[0]

        # 2. Hybrid search — returns candidate_k results
        candidates = await self._vector_store.search_hybrid(
            query_vec=query_vec,
            query_text=query,
            vs_ids=vs_ids,
            alpha=alpha,
            candidate_k=candidate_k,
        )

        if not candidates:
            return []

        # 3. Rerank candidates
        texts = [c.content for c in candidates]
        scores = await self._reranker.rerank(query, texts)

        # 4. Re-sort by reranker score and take top_k
        reranked = sorted(
            zip(candidates, scores, strict=False),
            key=lambda pair: pair[1],
            reverse=True,
        )
        top = reranked[:top_k]

        # 5. Return SearchResults with updated scores from reranker
        return [
            SearchResult(
                chunk_id=r.chunk_id,
                vector_store_id=r.vector_store_id,
                file_id=r.file_id,
                chunk_index=r.chunk_index,
                content=r.content,
                score=float(s),
                metadata=r.metadata,
            )
            for r, s in top
        ]
