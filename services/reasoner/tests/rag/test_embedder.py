"""Unit tests for sherlock.rag.adapters.embedder."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from sherlock.rag.adapters.embedder import EmbedderAdapter


def _make_mock_model(vectors: list[list[float]]) -> MagicMock:
    """Return a mock SentenceTransformer that returns the given vectors."""
    model = MagicMock()
    model.encode.return_value = np.array(vectors, dtype=np.float32)
    return model


class TestEmbedderAdapterEncode:
    def test_empty_input_returns_empty_list(self) -> None:
        model = MagicMock()
        adapter = EmbedderAdapter(model)
        result = adapter.encode([])
        assert result == []
        model.encode.assert_not_called()

    def test_single_text_returns_one_vector(self) -> None:
        vec = [0.1, 0.2, 0.3]
        model = _make_mock_model([vec])
        adapter = EmbedderAdapter(model)
        result = adapter.encode(["hello"])
        assert len(result) == 1
        assert result[0] == pytest.approx(vec, abs=1e-5)

    def test_multiple_texts_return_multiple_vectors(self) -> None:
        vecs = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        model = _make_mock_model(vecs)
        adapter = EmbedderAdapter(model)
        result = adapter.encode(["a", "b", "c"])
        assert len(result) == 3
        for i, expected in enumerate(vecs):
            assert result[i] == pytest.approx(expected, abs=1e-5)

    def test_encode_passes_convert_to_numpy_true(self) -> None:
        model = _make_mock_model([[0.0]])
        adapter = EmbedderAdapter(model)
        adapter.encode(["test"])
        model.encode.assert_called_once_with(["test"], convert_to_numpy=True)

    def test_result_is_list_of_lists(self) -> None:
        model = _make_mock_model([[0.1, 0.2], [0.3, 0.4]])
        adapter = EmbedderAdapter(model)
        result = adapter.encode(["x", "y"])
        assert isinstance(result, list)
        for row in result:
            assert isinstance(row, list)

    @pytest.mark.parametrize("n_texts", [1, 5, 10])
    def test_output_length_matches_input_length(self, n_texts: int) -> None:
        vecs = [[float(i)] * 4 for i in range(n_texts)]
        model = _make_mock_model(vecs)
        adapter = EmbedderAdapter(model)
        texts = [f"text {i}" for i in range(n_texts)]
        result = adapter.encode(texts)
        assert len(result) == n_texts
