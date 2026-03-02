"""LLM client factory with model-capability auto-detection.

Handles the prompt-template quirk where some instruction-tuned models
(Mistral instruct, Llama 2, Gemma, Phi) have no ``system`` slot in their
Jinja template and raise a 400 when a SystemMessage is passed.

Detection order:
  1. Explicit env var ``SHERLOCK_LLM_SUPPORTS_SYSTEM_ROLE`` — overrides everything.
  2. Model name heuristic — substring match against known non-system families.
  3. Default True — OpenAI / Anthropic / ChatML-based models all support it.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from sherlock.config import Settings

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
    """Return False if the model name matches a known no-system-role family."""
    lower = model_name.lower()
    return not any(family in lower for family in _NO_SYSTEM_ROLE_FAMILIES)


def create_llm(settings: Settings) -> tuple[ChatOpenAI, bool]:
    """Instantiate the LLM client and resolve system-role support.

    Returns:
        (llm, supports_system_role) — pass supports_system_role to build_graph.
    """
    if settings.llm_supports_system_role is None:
        # Auto-detect from model name
        supports_system_role = _detect_supports_system_role(settings.llm_model)
    else:
        # Explicit override via SHERLOCK_LLM_SUPPORTS_SYSTEM_ROLE
        supports_system_role = settings.llm_supports_system_role

    llm = ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key="lm-studio",
    )
    return llm, supports_system_role
