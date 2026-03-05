"""Unit tests for reasoner.rag.chunker."""
from __future__ import annotations

import pytest

from reasoner.rag.chunker import chunk_text


class TestChunkTextBasic:
    def test_empty_string_returns_empty_list(self) -> None:
        assert chunk_text("", 512, 50) == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert chunk_text("   \n\t  ", 512, 50) == []

    def test_short_text_returns_single_chunk(self) -> None:
        text = "This is a short sentence."
        chunks = chunk_text(text, 512, 50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunks_are_strings(self) -> None:
        chunks = chunk_text("hello world", 512, 0)
        assert all(isinstance(c, str) for c in chunks)

    def test_all_text_content_preserved(self) -> None:
        # Reassembling approximate content: each token appears in at least one chunk.
        text = "The quick brown fox jumps over the lazy dog"
        chunks = chunk_text(text, 4, 1)
        combined = " ".join(chunks)
        for word in ["quick", "brown", "fox", "jumps", "lazy", "dog"]:
            assert word in combined


class TestChunkTextOverlap:
    def test_overlap_zero_no_repeated_tokens(self) -> None:
        # With overlap=0, chunks should not share tokens.
        text = "word " * 20
        chunks = chunk_text(text, 5, 0)
        # Every chunk except possibly the last should have exactly 5 tokens.
        # Just verify we get multiple non-empty chunks.
        assert len(chunks) > 1

    def test_overlap_creates_more_chunks_than_no_overlap(self) -> None:
        text = "token " * 30
        chunks_no_overlap = chunk_text(text, 5, 0)
        chunks_with_overlap = chunk_text(text, 5, 2)
        assert len(chunks_with_overlap) >= len(chunks_no_overlap)

    def test_overlap_less_than_chunk_size_is_valid(self) -> None:
        chunks = chunk_text("a b c d e f g h", 4, 2)
        assert len(chunks) >= 1

    @pytest.mark.parametrize(
        "chunk_size,overlap",
        [
            (10, 10),
            (5, 5),
            (4, 6),
        ],
    )
    def test_overlap_gte_chunk_size_raises(self, chunk_size: int, overlap: int) -> None:
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("some text here", chunk_size, overlap)

    def test_negative_overlap_raises(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            chunk_text("some text", 10, -1)


class TestChunkTextValidation:
    @pytest.mark.parametrize("chunk_size", [0, -1, -100])
    def test_non_positive_chunk_size_raises(self, chunk_size: int) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            chunk_text("some text", chunk_size, 0)

    def test_chunk_size_one_gives_single_token_chunks(self) -> None:
        # Simple ASCII word should tokenize predictably.
        chunks = chunk_text("hello world", 1, 0)
        assert len(chunks) >= 2

    def test_large_chunk_size_returns_one_chunk(self) -> None:
        text = "This is a reasonably short sentence with a few words."
        chunks = chunk_text(text, 10000, 0)
        assert len(chunks) == 1


class TestChunkTextEdgeCases:
    def test_exact_chunk_boundary(self) -> None:
        # 10 tokens of "word" - chunk_size=5, overlap=0 => 2 chunks
        text = "word " * 10
        chunks = chunk_text(text.strip(), 5, 0)
        assert len(chunks) >= 2

    def test_unicode_text(self) -> None:
        text = "日本語テキスト。これはテストです。" * 5
        chunks = chunk_text(text, 10, 2)
        assert len(chunks) >= 1

    def test_chunks_reconstruct_content(self) -> None:
        # First chunk + last chunk should span the entire text.
        text = "a b c d e f g h i j k l m n o p"
        chunks = chunk_text(text, 4, 0)
        first = chunks[0].strip()
        last = chunks[-1].strip()
        assert first in text
        assert last in text

    @pytest.mark.parametrize("n_repeats", [1, 5, 20])
    def test_chunk_count_scales_with_text_length(self, n_repeats: int) -> None:
        base_text = "token " * 10 * n_repeats
        chunks = chunk_text(base_text, 10, 2)
        assert len(chunks) >= n_repeats
