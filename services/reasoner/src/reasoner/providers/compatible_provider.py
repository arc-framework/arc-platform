from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from reasoner.config import Settings
from reasoner.providers.base import LLMProviderPort

# Architecture families whose Jinja templates only accept user + assistant roles.
_NO_SYSTEM_ROLE_FAMILIES = (
    "mistral",
    "mixtral",
    "llama",
    "gemma",
    "phi",
    "falcon",
    "vicuna",
    "alpaca",
)


def _detect_supports_system_role(model_name: str) -> bool:
    """Return False if model name matches a known no-system-role family."""
    lower = model_name.lower()
    return not any(family in lower for family in _NO_SYSTEM_ROLE_FAMILIES)


class CompatibleProvider:
    """Default provider: any OpenAI-compatible endpoint (LM Studio, Ollama, vLLM, Groq)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_llm(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI  # lazy — preserves existing optional-dep behavior

        return ChatOpenAI(
            model=self._settings.llm_model,
            base_url=self._settings.llm_base_url,
            api_key=SecretStr(self._settings.llm_api_key or "lm-studio"),
        )

    def supports_system_role(self) -> bool:
        if self._settings.llm_supports_system_role is not None:
            return self._settings.llm_supports_system_role
        return _detect_supports_system_role(self._settings.llm_model)

    def provider_name(self) -> str:
        return "openai-compatible"


__all__ = ["CompatibleProvider", "LLMProviderPort"]
