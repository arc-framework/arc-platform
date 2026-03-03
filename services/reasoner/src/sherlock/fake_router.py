from __future__ import annotations

import random

from faker import Faker
from fastapi import APIRouter

_fake = Faker()

_MODELS = ["gpt-4o", "claude-3-5-sonnet", "gemini-2.0-flash"]

dev_router = APIRouter(prefix="/fake", tags=["dev"])


# ─── Legacy /chat fakes ───────────────────────────────────────────────────────


@dev_router.get("/chat", summary="Generate a fake /chat request body")
async def fake_chat_body() -> dict[str, str]:
    """Returns a randomised ChatRequest payload ready to POST to /chat."""
    return {
        "user_id": _fake.uuid4(),
        "text": _fake.sentence(nb_words=10),
    }


@dev_router.get("/chat/batch", summary="Generate N fake /chat request bodies")
async def fake_chat_batch(n: int = 5) -> list[dict[str, str]]:
    """Returns a list of N randomised ChatRequest payloads (max 20)."""
    count = min(n, 20)
    return [{"user_id": _fake.uuid4(), "text": _fake.sentence(nb_words=10)} for _ in range(count)]


# ─── v1 chat completions fakes ────────────────────────────────────────────────


@dev_router.get("/v1/chat/completions", summary="Generate a fake POST /v1/chat/completions body")
async def fake_v1_chat_completions() -> dict:
    """Returns a randomised ChatCompletionRequest payload (stream: false)."""
    return _chat_completion_payload(stream=False)


@dev_router.get(
    "/v1/chat/completions/stream",
    summary="Generate a fake POST /v1/chat/completions body (streaming)",
)
async def fake_v1_chat_completions_stream() -> dict:
    """Returns a randomised ChatCompletionRequest payload with stream: true."""
    return _chat_completion_payload(stream=True)


@dev_router.get("/v1/responses", summary="Generate a fake POST /v1/responses body")
async def fake_v1_responses() -> dict:
    """Returns a randomised ResponsesRequest payload ready to POST to /v1/responses."""
    return {
        "model": random.choice(_MODELS),
        "input": _fake.sentence(nb_words=12),
        "instructions": _fake.sentence(nb_words=8) if random.random() > 0.5 else None,
        "temperature": round(random.uniform(0.0, 1.0), 2),
        "max_output_tokens": random.choice([256, 512, 1024, 2048]),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _chat_completion_payload(*, stream: bool) -> dict:
    include_system = random.random() > 0.5
    messages = []
    if include_system:
        messages.append({"role": "system", "content": _fake.sentence(nb_words=8)})
    messages.append({"role": "user", "content": _fake.sentence(nb_words=12)})
    if random.random() > 0.7:
        messages.append({"role": "assistant", "content": _fake.sentence(nb_words=10)})
        messages.append({"role": "user", "content": _fake.sentence(nb_words=8)})

    return {
        "model": random.choice(_MODELS),
        "messages": messages,
        "stream": stream,
        "temperature": round(random.uniform(0.0, 1.0), 2),
        "max_tokens": random.choice([256, 512, 1024, 2048]),
    }
