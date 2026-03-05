from __future__ import annotations

import asyncio
import threading

import structlog
from sentence_transformers import CrossEncoder

from reasoner.config import Settings

_log = structlog.get_logger(__name__)


class RerankerAdapter:
    """RerankerPort backed by a lazily-loaded CrossEncoder model."""

    _instance: CrossEncoder | None = None  # class-level cache, shared across all instances
    _lock: threading.Lock = threading.Lock()

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.reranker_model

    async def rerank(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        model = await asyncio.to_thread(self._get_or_load_model)
        pairs = [(query, t) for t in texts]
        raw = await asyncio.to_thread(lambda: model.predict(pairs))
        scores: list[float] = raw.tolist()
        return scores

    def _get_or_load_model(self) -> CrossEncoder:
        if RerankerAdapter._instance is None:
            with RerankerAdapter._lock:
                if RerankerAdapter._instance is None:  # double-checked locking
                    _log.info("reranker.loading", model=self._model_name)
                    RerankerAdapter._instance = CrossEncoder(self._model_name)
                    _log.info("reranker.loaded", model=self._model_name)
        return RerankerAdapter._instance
