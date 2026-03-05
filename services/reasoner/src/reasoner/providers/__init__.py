from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reasoner.config import Settings
    from reasoner.providers.base import LLMProviderPort


def create_provider(settings: Settings) -> LLMProviderPort:
    from reasoner.providers.factory import create_provider as _create

    return _create(settings)


__all__ = ["create_provider"]
