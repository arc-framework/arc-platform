from __future__ import annotations

from reasoner.config import Settings
from reasoner.providers.anthropic_provider import AnthropicProvider
from reasoner.providers.base import LLMProviderPort
from reasoner.providers.compatible_provider import CompatibleProvider
from reasoner.providers.google_provider import GoogleProvider
from reasoner.providers.openai_provider import OpenAIProvider


def create_provider(settings: Settings) -> LLMProviderPort:
    """Select and instantiate the configured LLM provider.

    Unknown provider values fall back to CompatibleProvider (default behavior).
    """
    match settings.llm_provider:
        case "openai":
            return OpenAIProvider(settings)
        case "anthropic":
            return AnthropicProvider(settings)
        case "google":
            return GoogleProvider(settings)
        case _:
            return CompatibleProvider(settings)
