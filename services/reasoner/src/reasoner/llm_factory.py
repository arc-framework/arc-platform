"""Backward-compatible LLM factory shim.

Delegates to providers/factory.py — see that module for the full implementation.
The call signature create_llm(settings) -> (BaseChatModel, bool) is preserved
for existing callers (main.py) without modification.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from reasoner.config import Settings


def create_llm(settings: Settings) -> tuple[BaseChatModel, bool]:
    """Instantiate the configured LLM and return (llm, supports_system_role)."""
    from reasoner.providers import create_provider

    provider = create_provider(settings)
    return provider.create_llm(), provider.supports_system_role()
