from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── Shared ───────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# ─── POST /v1/chat/completions — Request ──────────────────────────────────────


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1)
    top_p: float | None = Field(None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    stop: str | list[str] | None = None
    user: str | None = None
    # n=1 only — multi-completion not supported; Field(le=1) enforces the limit
    n: int = Field(1, ge=1, le=1)
    tools: list[dict[str, Any]] | None = None


# ─── POST /v1/chat/completions — Sync Response ────────────────────────────────


class ChoiceDelta(BaseModel):
    role: str | None = None
    content: str | None = None


class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] | None = "stop"
    logprobs: None = None


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: UsageInfo
    system_fingerprint: str | None = None


# ─── POST /v1/chat/completions — SSE Streaming Chunks ─────────────────────────


class StreamChoice(BaseModel):
    index: int = 0
    delta: ChoiceDelta
    finish_reason: Literal["stop", "length", "content_filter"] | None = None
    logprobs: None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]
    usage: UsageInfo | None = None


# ─── POST /v1/responses ───────────────────────────────────────────────────────


class ResponseInputItem(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ResponseOutputContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str


class ResponseOutputItem(BaseModel):
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[ResponseOutputContent]
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    status: Literal["completed", "failed", "in_progress"] = "completed"


class ResponsesRequest(BaseModel):
    model: str
    input: str | list[ResponseInputItem]
    instructions: str | None = None
    user: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    stream: bool = False


class ResponsesUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ResponsesResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"resp_{uuid.uuid4().hex}")
    object: Literal["response"] = "response"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    model: str
    output: list[ResponseOutputItem]
    usage: ResponsesUsage
    status: Literal["completed", "failed", "in_progress"] = "completed"
    instructions: str | None = None


# ─── GET /v1/models ───────────────────────────────────────────────────────────


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "arc-platform"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]
