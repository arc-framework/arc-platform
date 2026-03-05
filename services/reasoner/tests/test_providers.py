"""Tests for the provider factory and all 4 LLM provider implementations."""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from reasoner.config import Settings
from reasoner.providers.anthropic_provider import AnthropicProvider
from reasoner.providers.base import LLMProviderPort
from reasoner.providers.compatible_provider import CompatibleProvider
from reasoner.providers.factory import create_provider
from reasoner.providers.google_provider import GoogleProvider
from reasoner.providers.openai_provider import OpenAIProvider


# ─── Helpers ──────────────────────────────────────────────────────────────────


def make_settings(**overrides: object) -> Settings:
    """Create Settings with env var overrides, clearing only SHERLOCK_ keys we set."""
    env: dict[str, str] = {
        "SHERLOCK_LLM_PROVIDER": "openai-compatible",
        "SHERLOCK_LLM_API_KEY": "",
    }
    for k, v in overrides.items():
        env[f"SHERLOCK_{k.upper()}"] = str(v)
    with patch.dict(os.environ, env, clear=False):
        return Settings()


# ─── create_provider: correct class per provider name ─────────────────────────


def test_create_provider_openai() -> None:
    """create_provider returns OpenAIProvider when llm_provider='openai'."""
    settings = make_settings(llm_provider="openai", llm_api_key="sk-test")
    provider = create_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_create_provider_anthropic() -> None:
    """create_provider returns AnthropicProvider when llm_provider='anthropic'."""
    settings = make_settings(llm_provider="anthropic", llm_api_key="sk-ant-test")
    provider = create_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_create_provider_google() -> None:
    """create_provider returns GoogleProvider when llm_provider='google'."""
    settings = make_settings(llm_provider="google", llm_api_key="AIza-test")
    provider = create_provider(settings)
    assert isinstance(provider, GoogleProvider)


def test_create_provider_compatible_explicit() -> None:
    """create_provider returns CompatibleProvider when llm_provider='openai-compatible'."""
    settings = make_settings(llm_provider="openai-compatible")
    provider = create_provider(settings)
    assert isinstance(provider, CompatibleProvider)


def test_create_provider_unknown_falls_back_to_compatible() -> None:
    """Unknown llm_provider value falls back to CompatibleProvider."""
    settings = make_settings(llm_provider="unknown-provider-xyz")
    provider = create_provider(settings)
    assert isinstance(provider, CompatibleProvider)


def test_create_provider_empty_string_falls_back_to_compatible() -> None:
    """Empty string llm_provider falls back to CompatibleProvider."""
    settings = make_settings(llm_provider="ollama")
    provider = create_provider(settings)
    assert isinstance(provider, CompatibleProvider)


# ─── ValueError when api key missing ──────────────────────────────────────────


def test_openai_provider_raises_when_api_key_empty() -> None:
    """OpenAIProvider raises ValueError when llm_api_key is empty."""
    settings = make_settings(llm_provider="openai", llm_api_key="")
    with pytest.raises(ValueError, match="SHERLOCK_LLM_API_KEY"):
        OpenAIProvider(settings)


def test_anthropic_provider_raises_when_api_key_empty() -> None:
    """AnthropicProvider raises ValueError when llm_api_key is empty."""
    settings = make_settings(llm_provider="anthropic", llm_api_key="")
    with pytest.raises(ValueError, match="SHERLOCK_LLM_API_KEY"):
        AnthropicProvider(settings)


def test_google_provider_raises_when_api_key_empty() -> None:
    """GoogleProvider raises ValueError when llm_api_key is empty."""
    settings = make_settings(llm_provider="google", llm_api_key="")
    with pytest.raises(ValueError, match="SHERLOCK_LLM_API_KEY"):
        GoogleProvider(settings)


# ─── ImportError when optional dep missing ────────────────────────────────────


def test_anthropic_provider_importerror_when_dep_absent() -> None:
    """AnthropicProvider.create_llm() raises ImportError when langchain-anthropic absent."""
    settings = make_settings(llm_provider="anthropic", llm_api_key="sk-ant-test")
    provider = AnthropicProvider(settings)
    with patch.dict(sys.modules, {"langchain_anthropic": None}):
        with pytest.raises(ImportError, match="langchain-anthropic"):
            provider.create_llm()


def test_google_provider_importerror_when_dep_absent() -> None:
    """GoogleProvider.create_llm() raises ImportError when langchain-google-genai absent."""
    settings = make_settings(llm_provider="google", llm_api_key="AIza-test")
    provider = GoogleProvider(settings)
    with patch.dict(sys.modules, {"langchain_google_genai": None}):
        with pytest.raises(ImportError, match="langchain-google-genai"):
            provider.create_llm()


# ─── CompatibleProvider.supports_system_role — no-system-role families ────────


@pytest.mark.parametrize(
    "model_name",
    [
        "mistralai/mistral-7b-instruct-v0.3",
        "meta-llama/llama-3-8b-instruct",
        "google/gemma-2b",
        "microsoft/phi-2",
        "tiiuae/falcon-7b-instruct",
        "lmsys/vicuna-13b-v1.5",
        "chavinlo/alpaca-native",
        "mistral-small",
        "mixtral-8x7b-instruct",
    ],
)
def test_compatible_supports_system_role_false_for_no_system_families(
    model_name: str,
) -> None:
    """CompatibleProvider.supports_system_role() returns False for no-system-role families."""
    settings = make_settings(llm_model=model_name)
    provider = CompatibleProvider(settings)
    assert provider.supports_system_role() is False


# ─── CompatibleProvider.supports_system_role — other models ──────────────────


@pytest.mark.parametrize(
    "model_name",
    [
        "gpt-4o",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "command-r",
        "deepseek-coder",
        "starcoder2-7b",
    ],
)
def test_compatible_supports_system_role_true_for_other_models(
    model_name: str,
) -> None:
    """CompatibleProvider.supports_system_role() returns True for models outside no-system families."""
    settings = make_settings(llm_model=model_name)
    provider = CompatibleProvider(settings)
    assert provider.supports_system_role() is True


# ─── CompatibleProvider.supports_system_role — explicit override ──────────────


def test_compatible_supports_system_role_override_true() -> None:
    """llm_supports_system_role=True overrides auto-detection even for mistral."""
    env = {
        "SHERLOCK_LLM_PROVIDER": "openai-compatible",
        "SHERLOCK_LLM_API_KEY": "",
        "SHERLOCK_LLM_MODEL": "mistralai/mistral-7b-instruct-v0.3",
        "SHERLOCK_LLM_SUPPORTS_SYSTEM_ROLE": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = Settings()
    provider = CompatibleProvider(settings)
    assert provider.supports_system_role() is True


def test_compatible_supports_system_role_override_false() -> None:
    """llm_supports_system_role=False overrides auto-detection even for gpt-4o."""
    env = {
        "SHERLOCK_LLM_PROVIDER": "openai-compatible",
        "SHERLOCK_LLM_API_KEY": "",
        "SHERLOCK_LLM_MODEL": "gpt-4o",
        "SHERLOCK_LLM_SUPPORTS_SYSTEM_ROLE": "false",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = Settings()
    provider = CompatibleProvider(settings)
    assert provider.supports_system_role() is False


# ─── isinstance checks — all providers satisfy LLMProviderPort ────────────────


def test_compatible_provider_satisfies_protocol() -> None:
    """CompatibleProvider is an instance of LLMProviderPort."""
    settings = make_settings()
    provider = CompatibleProvider(settings)
    assert isinstance(provider, LLMProviderPort)


def test_openai_provider_satisfies_protocol() -> None:
    """OpenAIProvider is an instance of LLMProviderPort."""
    settings = make_settings(llm_api_key="sk-test")
    provider = OpenAIProvider(settings)
    assert isinstance(provider, LLMProviderPort)


def test_anthropic_provider_satisfies_protocol() -> None:
    """AnthropicProvider is an instance of LLMProviderPort."""
    settings = make_settings(llm_api_key="sk-ant-test")
    provider = AnthropicProvider(settings)
    assert isinstance(provider, LLMProviderPort)


def test_google_provider_satisfies_protocol() -> None:
    """GoogleProvider is an instance of LLMProviderPort."""
    settings = make_settings(llm_api_key="AIza-test")
    provider = GoogleProvider(settings)
    assert isinstance(provider, LLMProviderPort)


# ─── provider_name() correctness ─────────────────────────────────────────────


def test_compatible_provider_name() -> None:
    """CompatibleProvider.provider_name() returns 'openai-compatible'."""
    settings = make_settings()
    assert CompatibleProvider(settings).provider_name() == "openai-compatible"


def test_openai_provider_name() -> None:
    """OpenAIProvider.provider_name() returns 'openai'."""
    settings = make_settings(llm_api_key="sk-test")
    assert OpenAIProvider(settings).provider_name() == "openai"


def test_anthropic_provider_name() -> None:
    """AnthropicProvider.provider_name() returns 'anthropic'."""
    settings = make_settings(llm_api_key="sk-ant-test")
    assert AnthropicProvider(settings).provider_name() == "anthropic"


def test_google_provider_name() -> None:
    """GoogleProvider.provider_name() returns 'google'."""
    settings = make_settings(llm_api_key="AIza-test")
    assert GoogleProvider(settings).provider_name() == "google"


# ─── supports_system_role() always True for non-compatible providers ──────────


def test_openai_provider_supports_system_role() -> None:
    """OpenAIProvider.supports_system_role() always returns True."""
    settings = make_settings(llm_api_key="sk-test")
    assert OpenAIProvider(settings).supports_system_role() is True


def test_anthropic_provider_supports_system_role() -> None:
    """AnthropicProvider.supports_system_role() always returns True."""
    settings = make_settings(llm_api_key="sk-ant-test")
    assert AnthropicProvider(settings).supports_system_role() is True


def test_google_provider_supports_system_role() -> None:
    """GoogleProvider.supports_system_role() always returns True."""
    settings = make_settings(llm_api_key="AIza-test")
    assert GoogleProvider(settings).supports_system_role() is True


# ─── create_provider returns LLMProviderPort for all known values ─────────────


@pytest.mark.parametrize(
    "provider_value,api_key",
    [
        ("openai", "sk-test"),
        ("anthropic", "sk-ant-test"),
        ("google", "AIza-test"),
        ("openai-compatible", ""),
        ("unknown", ""),
    ],
)
def test_create_provider_always_returns_llm_provider_port(
    provider_value: str, api_key: str
) -> None:
    """create_provider always returns an LLMProviderPort regardless of provider value."""
    settings = make_settings(llm_provider=provider_value, llm_api_key=api_key)
    provider = create_provider(settings)
    assert isinstance(provider, LLMProviderPort)
