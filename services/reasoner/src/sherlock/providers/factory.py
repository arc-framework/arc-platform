from __future__ import annotations

from sherlock.config import Settings
from sherlock.providers.anthropic_provider import AnthropicProvider
from sherlock.providers.base import LLMProviderPort
from sherlock.providers.compatible_provider import CompatibleProvider
from sherlock.providers.google_provider import GoogleProvider
from sherlock.providers.openai_provider import OpenAIProvider


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
