from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

from sherlock.config import Settings


class OpenAIProvider:
    """OpenAI direct provider (api.openai.com) or Azure OpenAI (via openai_base_url)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError(
                "SHERLOCK_LLM_API_KEY is required for llm_provider='openai'. "
                "Set it to your OpenAI API key (sk-...)."
            )
        self._settings = settings

    def create_llm(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI  # lazy import

        kwargs: dict[str, Any] = {
            "model": self._settings.llm_model,
            "api_key": self._settings.llm_api_key,
        }
        if self._settings.openai_base_url:
            kwargs["base_url"] = self._settings.openai_base_url
        return ChatOpenAI(**kwargs)

    def supports_system_role(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "openai"


__all__ = ["OpenAIProvider"]
