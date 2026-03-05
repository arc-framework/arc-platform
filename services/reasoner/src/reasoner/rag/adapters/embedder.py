from __future__ import annotations

import structlog
from sentence_transformers import SentenceTransformer

_log = structlog.get_logger(__name__)


class EmbedderAdapter:
    """EmbedderPort backed by an injected SentenceTransformer model."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._model.encode(texts, convert_to_numpy=True)
        return result.tolist()  # type: ignore[no-any-return]
