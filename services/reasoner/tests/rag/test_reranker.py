"""Unit tests for sherlock.rag.adapters.reranker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sherlock.rag.adapters.reranker import RerankerAdapter


def _make_settings(model_name: str = "cross-encoder/test-model") -> MagicMock:
    s = MagicMock()
    s.reranker_model = model_name
    return s


class TestRerankerAdapterRerank:
    def setup_method(self) -> None:
        # Reset the class-level singleton between tests.
        RerankerAdapter._instance = None

    async def test_empty_texts_returns_empty_list(self) -> None:
        settings = _make_settings()
        adapter = RerankerAdapter(settings)
        result = await adapter.rerank("query", [])
        assert result == []

    async def test_rerank_returns_scores_list(self) -> None:
        settings = _make_settings()
        adapter = RerankerAdapter(settings)

        mock_cross_encoder = MagicMock()
        mock_cross_encoder.predict.return_value = np.array([0.9, 0.4, 0.7])

        with patch.object(adapter, "_get_or_load_model", return_value=mock_cross_encoder):
            scores = await adapter.rerank("my query", ["text a", "text b", "text c"])

        assert len(scores) == 3
        assert scores[0] == pytest.approx(0.9, abs=1e-5)
        assert scores[1] == pytest.approx(0.4, abs=1e-5)
        assert scores[2] == pytest.approx(0.7, abs=1e-5)

    async def test_rerank_builds_correct_pairs(self) -> None:
        settings = _make_settings()
        adapter = RerankerAdapter(settings)

        mock_ce = MagicMock()
        mock_ce.predict.return_value = np.array([0.5, 0.6])

        with patch.object(adapter, "_get_or_load_model", return_value=mock_ce):
            await adapter.rerank("question", ["answer1", "answer2"])

        call_args = mock_ce.predict.call_args[0][0]
        assert call_args == [("question", "answer1"), ("question", "answer2")]

    async def test_rerank_result_is_list_of_floats(self) -> None:
        settings = _make_settings()
        adapter = RerankerAdapter(settings)

        mock_ce = MagicMock()
        mock_ce.predict.return_value = np.array([0.1])

        with patch.object(adapter, "_get_or_load_model", return_value=mock_ce):
            scores = await adapter.rerank("q", ["t"])

        assert isinstance(scores, list)
        assert all(isinstance(s, float) for s in scores)

    def test_get_or_load_model_uses_double_checked_locking(self) -> None:
        settings = _make_settings("my-model")

        mock_instance = MagicMock()
        with patch("sherlock.rag.adapters.reranker.CrossEncoder", return_value=mock_instance):
            adapter = RerankerAdapter(settings)
            result1 = adapter._get_or_load_model()
            result2 = adapter._get_or_load_model()

        # Both calls return the same cached instance.
        assert result1 is result2
        assert RerankerAdapter._instance is mock_instance

    @pytest.mark.parametrize("n_texts", [1, 3, 5])
    async def test_score_count_matches_text_count(self, n_texts: int) -> None:
        settings = _make_settings()
        adapter = RerankerAdapter(settings)

        mock_ce = MagicMock()
        mock_ce.predict.return_value = np.ones(n_texts)

        texts = [f"doc {i}" for i in range(n_texts)]
        with patch.object(adapter, "_get_or_load_model", return_value=mock_ce):
            scores = await adapter.rerank("query", texts)

        assert len(scores) == n_texts
