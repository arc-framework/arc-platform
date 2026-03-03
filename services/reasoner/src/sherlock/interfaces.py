from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from langchain_core.language_models import BaseChatModel

from sherlock.models_v1 import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelList,
    ResponsesRequest,
    ResponsesResponse,
)

# ─── Provider Layer ────────────────────────────────────────────────────────────


@runtime_checkable
class LLMProviderPort(Protocol):
    """Factory interface — returns a configured BaseChatModel for the graph."""

    def create_llm(self) -> BaseChatModel: ...

    def supports_system_role(self) -> bool: ...

    def provider_name(self) -> str: ...


# ─── HTTP API Layer ────────────────────────────────────────────────────────────


@runtime_checkable
class ChatCompletionPort(Protocol):
    """Synchronous /v1/chat/completions handler."""

    async def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse: ...


@runtime_checkable
class StreamingPort(Protocol):
    """SSE streaming adapter — returns an async iterator of completion chunks.

    Implementations are typically async generator functions whose sync wrapper
    returns the generator object (which satisfies AsyncIterator[ChatCompletionChunk]).
    """

    def stream(self, req: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]: ...


@runtime_checkable
class ModelRegistryPort(Protocol):
    """Read-only model registry backing GET /v1/models."""

    def list_models(self) -> ModelList: ...

    def model_exists(self, model_id: str) -> bool: ...


@runtime_checkable
class ResponsesPort(Protocol):
    """Handler for POST /v1/responses (Responses API)."""

    async def respond(self, req: ResponsesRequest) -> ResponsesResponse: ...


# ─── Infrastructure Layer ──────────────────────────────────────────────────────


@runtime_checkable
class AsyncDocPort(Protocol):
    """Provides the filesystem path to the static AsyncAPI HTML docs directory.

    Returns None when the directory has not been built (local dev without Docker).
    The router serves a 404 JSON in that case (TD-6 dev fallback).
    """

    def get_docs_path(self) -> str | None: ...


@runtime_checkable
class OpenAINATSPort(Protocol):
    """NATS v1 chat handler — subscribes to sherlock.v1.chat, publishes to sherlock.v1.result."""

    async def connect(self) -> None: ...

    async def subscribe(self) -> None: ...

    def is_connected(self) -> bool: ...

    async def close(self) -> None: ...
