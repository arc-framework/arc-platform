from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from reasoner.config import Settings
from reasoner.providers.base import LLMProviderPort


class GoogleProvider:
    """Google Gemini provider (AI Studio or Vertex AI)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key:
            raise ValueError(
                "SHERLOCK_LLM_API_KEY is required for llm_provider='google'. "
                "Set it to your Google AI Studio API key (AIza...)."
            )
        self._settings = settings

    def create_llm(self) -> BaseChatModel:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # lazy — optional dep
        except ImportError as exc:
            raise ImportError(
                "langchain-google-genai is not installed. "
                "Install it with: pip install 'langchain-google-genai>=2.0'"
            ) from exc

        kwargs: dict[str, str] = {
            "model": self._settings.llm_model,
            "google_api_key": self._settings.llm_api_key,
        }
        if self._settings.google_project_id:
            kwargs["project"] = self._settings.google_project_id

        return ChatGoogleGenerativeAI(**kwargs)

    def supports_system_role(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "google"


__all__ = ["GoogleProvider", "LLMProviderPort"]
