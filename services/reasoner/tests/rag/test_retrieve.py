"""Unit tests for sherlock.rag.application.retrieve.HybridRetriever."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sherlock.rag.application.retrieve import HybridRetriever
from sherlock.rag.domain.models import SearchResult


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_search_result(
    chunk_id: str = "c-1",
    vector_store_id: str = "vs-1",
    file_id: str = "f-1",
    content: str = "result content",
    score: float = 0.8,
    chunk_index: int = 0,
) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        vector_store_id=vector_store_id,
        file_id=file_id,
        content=content,
        score=score,
        chunk_index=chunk_index,
    )


def _make_retriever(
    candidates: list[SearchResult] | None = None,
    rerank_scores: list[float] | None = None,
    query_vec: list[float] | None = None,
) -> HybridRetriever:
    vector_store = AsyncMock()
    vector_store.search_hybrid.return_value = candidates or []

    embedder = MagicMock()
    embedder.encode.return_value = [query_vec or [0.1, 0.2, 0.3]]

    reranker = AsyncMock()
    reranker.rerank.return_value = rerank_scores or []

    return HybridRetriever(
        vector_store=vector_store,
        embedder=embedder,
        reranker=reranker,
    )


# ─── Early-exit guards ────────────────────────────────────────────────────────


class TestHybridRetrieverGuards:
    async def test_empty_vs_ids_returns_empty(self) -> None:
        retriever = _make_retriever()
        results = await retriever.search("query", [], 0.7, 50, 5)
        assert results == []

    async def test_blank_query_returns_empty(self) -> None:
        retriever = _make_retriever()
        results = await retriever.search("   ", ["vs-1"], 0.7, 50, 5)
        assert results == []

    async def test_empty_query_returns_empty(self) -> None:
        retriever = _make_retriever()
        results = await retriever.search("", ["vs-1"], 0.7, 50, 5)
        assert results == []

    async def test_no_candidates_returns_empty(self) -> None:
        retriever = _make_retriever(candidates=[], rerank_scores=[])
        results = await retriever.search("find something", ["vs-1"], 0.7, 50, 5)
        assert results == []


# ─── Normal search flow ───────────────────────────────────────────────────────


class TestHybridRetrieverSearch:
    async def test_search_returns_search_results(self) -> None:
        candidates = [_make_search_result(chunk_id="c-1", content="relevant")]
        retriever = _make_retriever(candidates=candidates, rerank_scores=[0.9])

        results = await retriever.search("my query", ["vs-1"], 0.7, 50, 5)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)

    async def test_search_calls_embedder_encode(self) -> None:
        vector_store = AsyncMock()
        vector_store.search_hybrid.return_value = []
        embedder = MagicMock()
        embedder.encode.return_value = [[0.5, 0.6]]
        reranker = AsyncMock()
        reranker.rerank.return_value = []

        retriever = HybridRetriever(vector_store, embedder, reranker)
        await retriever.search("test query", ["vs-1"], 0.7, 50, 5)

        embedder.encode.assert_called_once_with(["test query"])

    async def test_search_passes_alpha_and_candidate_k(self) -> None:
        vector_store = AsyncMock()
        vector_store.search_hybrid.return_value = []
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1]]
        reranker = AsyncMock()
        reranker.rerank.return_value = []

        retriever = HybridRetriever(vector_store, embedder, reranker)
        await retriever.search("query", ["vs-a", "vs-b"], alpha=0.5, candidate_k=25, top_k=3)

        vector_store.search_hybrid.assert_called_once_with(
            query_vec=[0.1],
            query_text="query",
            vs_ids=["vs-a", "vs-b"],
            alpha=0.5,
            candidate_k=25,
        )

    async def test_top_k_limits_returned_results(self) -> None:
        candidates = [
            _make_search_result(chunk_id=f"c-{i}", content=f"doc {i}", score=float(i))
            for i in range(10)
        ]
        scores = [float(i) for i in range(10)]
        retriever = _make_retriever(candidates=candidates, rerank_scores=scores)

        results = await retriever.search("query", ["vs-1"], 0.7, 50, top_k=3)

        assert len(results) == 3

    async def test_results_sorted_by_reranker_score_descending(self) -> None:
        candidates = [
            _make_search_result(chunk_id="c-low", content="low relevance", score=0.9),
            _make_search_result(chunk_id="c-high", content="high relevance", score=0.1),
        ]
        # Reranker gives c-low a lower score and c-high a higher score.
        rerank_scores = [0.2, 0.95]
        retriever = _make_retriever(candidates=candidates, rerank_scores=rerank_scores)

        results = await retriever.search("query", ["vs-1"], 0.7, 50, top_k=2)

        assert results[0].chunk_id == "c-high"
        assert results[1].chunk_id == "c-low"

    async def test_scores_updated_from_reranker(self) -> None:
        candidates = [_make_search_result(chunk_id="c-1", score=0.5)]
        rerank_scores = [0.88]
        retriever = _make_retriever(candidates=candidates, rerank_scores=rerank_scores)

        results = await retriever.search("query", ["vs-1"], 0.7, 50, top_k=1)

        assert results[0].score == pytest.approx(0.88, abs=1e-5)

    async def test_result_fields_preserved(self) -> None:
        candidates = [
            _make_search_result(
                chunk_id="chunk-xyz",
                vector_store_id="vs-abc",
                file_id="file-def",
                content="the content",
                chunk_index=7,
            )
        ]
        retriever = _make_retriever(candidates=candidates, rerank_scores=[0.75])

        results = await retriever.search("q", ["vs-abc"], 0.7, 10, top_k=1)

        r = results[0]
        assert r.chunk_id == "chunk-xyz"
        assert r.vector_store_id == "vs-abc"
        assert r.file_id == "file-def"
        assert r.content == "the content"
        assert r.chunk_index == 7

    async def test_reranker_called_with_query_and_content(self) -> None:
        vector_store = AsyncMock()
        candidates = [
            _make_search_result(chunk_id="c-1", content="first doc"),
            _make_search_result(chunk_id="c-2", content="second doc"),
        ]
        vector_store.search_hybrid.return_value = candidates

        embedder = MagicMock()
        embedder.encode.return_value = [[0.1]]

        reranker = AsyncMock()
        reranker.rerank.return_value = [0.7, 0.3]

        retriever = HybridRetriever(vector_store, embedder, reranker)
        await retriever.search("my question", ["vs-1"], 0.7, 50, 2)

        reranker.rerank.assert_called_once_with("my question", ["first doc", "second doc"])

    @pytest.mark.parametrize("top_k", [1, 2, 5])
    async def test_top_k_parametrized(self, top_k: int) -> None:
        n_candidates = 10
        candidates = [
            _make_search_result(chunk_id=f"c-{i}", score=float(i))
            for i in range(n_candidates)
        ]
        scores = [float(i) for i in range(n_candidates)]
        retriever = _make_retriever(candidates=candidates, rerank_scores=scores)

        results = await retriever.search("q", ["vs-1"], 0.7, 50, top_k)
        assert len(results) == min(top_k, n_candidates)

    async def test_multiple_vs_ids_passed_to_vector_store(self) -> None:
        vector_store = AsyncMock()
        vector_store.search_hybrid.return_value = []
        embedder = MagicMock()
        embedder.encode.return_value = [[0.1]]
        reranker = AsyncMock()
        reranker.rerank.return_value = []

        retriever = HybridRetriever(vector_store, embedder, reranker)
        vs_ids = ["vs-1", "vs-2", "vs-3"]
        await retriever.search("query", vs_ids, 0.7, 50, 5)

        call_kwargs = vector_store.search_hybrid.call_args.kwargs
        assert call_kwargs["vs_ids"] == vs_ids
