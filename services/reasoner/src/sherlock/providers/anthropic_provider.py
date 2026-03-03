from __future__ import annotations

from typing import cast

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from sherlock.config import Settings
from sherlock.providers.base import LLMProviderPort


class AnthropicProvider:
    """Anthropic Claude provider (api.anthropic.com)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError(
                "SHERLOCK_LLM_API_KEY is required for llm_provider='anthropic'. "
                "Set it to your Anthropic API key (sk-ant-...)."
            )
        self._settings = settings

    def create_llm(self) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic  # lazy — optional dep
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is not installed. "
                "Install it with: pip install 'langchain-anthropic>=0.3'"
            ) from exc

        return cast(
            BaseChatModel,
            ChatAnthropic(
                model_name=self._settings.llm_model,  # type: ignore[call-arg]
                api_key=SecretStr(self._settings.llm_api_key),
            ),
        )

    def supports_system_role(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "anthropic"


__all__ = ["AnthropicProvider", "LLMProviderPort"]
