"""Token-aware text chunker using tiktoken cl100k_base encoding."""
from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping token-based chunks.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum tokens per chunk.
        overlap: Token overlap between consecutive chunks.

    Returns:
        List of text chunks. Empty list if text is empty.
    """
    if not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    if overlap < 0:
        raise ValueError(f"overlap must be non-negative, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    stride = chunk_size - overlap  # step between chunk starts

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_ENCODING.decode(chunk_tokens))
        if end == len(tokens):
            break
        start += stride

    return chunks
