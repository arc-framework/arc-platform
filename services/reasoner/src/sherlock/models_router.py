from __future__ import annotations

from fastapi import APIRouter

from sherlock.config import Settings
from sherlock.interfaces import ModelRegistryPort
from sherlock.models_v1 import ModelList, ModelObject


class StaticModelRegistry:
    """Single-model registry backed by SHERLOCK_LLM_MODEL setting."""

    def __init__(self, settings: Settings) -> None:
        self._model_id = settings.llm_model

    def list_models(self) -> ModelList:
        return ModelList(data=[ModelObject(id=self._model_id)])

    def model_exists(self, model_id: str) -> bool:
        return model_id == self._model_id


def build_models_router(registry: ModelRegistryPort) -> APIRouter:
    """Return an APIRouter with GET /models. Mount with prefix=/v1 in main.py."""
    router = APIRouter(tags=["models"])

    @router.get("/models", response_model=ModelList)
    async def list_models() -> ModelList:
        return registry.list_models()

    return router
