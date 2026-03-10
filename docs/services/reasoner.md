---
url: /arc-platform/docs/services/reasoner.md
---
# Reasoner — Sherlock

LangGraph reasoning engine with pgvector memory, OpenAI-compatible HTTP API, and NATS async transport.

| Field | Value |
|-------|-------|
| Codename | Sherlock |
| Container | `arc-reasoner` |
| Port | 8802 |
| Health URL | `http://localhost:8802/health` |
| Profiles | reason, ultra-instinct |
| Source | `services/reasoner/` |

## Make Targets

```bash
make reasoner-up       # start arc-reasoner container
make reasoner-down     # stop arc-reasoner container
make reasoner-health   # curl /health
make reasoner-logs     # follow container logs
make reasoner-test     # run pytest suite
make reasoner-lint     # ruff + mypy
```

## HTTP API

All OpenAI-compatible routes are mounted under the `/v1` prefix. The legacy `/chat` endpoint remains available for internal use.

### POST /v1/chat/completions

OpenAI-compatible chat completions. Supports both synchronous and streaming (`"stream": true`) responses.

**Sync request:**

```bash
curl -s http://localhost:8802/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "What is the ARC platform?"}
    ]
  }'
```

**Sync response:**

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "claude-3-5-sonnet-20241022",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The ARC platform is ..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 48,
    "total_tokens": 60
  }
}
```

**Streaming request:**

```bash
curl -s http://localhost:8802/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "Explain LangGraph in one sentence."}
    ],
    "stream": true
  }'
```

**Streaming response** (Server-Sent Events):

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Lang"},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Graph"},"index":0}]}

data: [DONE]
```

**RAG via file\_search tool** (requires `rag_enabled=true`):

```json
{
  "model": "claude-3-5-sonnet-20241022",
  "messages": [{"role": "user", "content": "Summarize the uploaded document."}],
  "tools": [
    {
      "type": "file_search",
      "vector_store_ids": ["vs_abc123"],
      "hybrid_alpha": 0.5
    }
  ]
}
```

***

### POST /v1/responses

OpenAI Responses API. Accepts either a plain string or a structured input array.

```bash
curl -s http://localhost:8802/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "input": "What is the capital of France?"
  }'
```

**Response:**

```json
{
  "id": "resp-...",
  "object": "response",
  "model": "claude-3-5-sonnet-20241022",
  "output": [
    {
      "type": "message",
      "content": [{"type": "output_text", "text": "Paris."}]
    }
  ],
  "usage": {
    "input_tokens": 8,
    "output_tokens": 2,
    "total_tokens": 10
  }
}
```

***

### GET /v1/models

List the active model configured for this instance.

```bash
curl -s http://localhost:8802/v1/models
```

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-3-5-sonnet-20241022",
      "object": "model"
    }
  ]
}
```

***

### Files API (RAG)

Requires `SHERLOCK_RAG_ENABLED=true`. Returns `503` when RAG is not enabled.

Supported file types: `.txt`, `.md`, `.rst`, `.py`, `.go`, `.ts`, `.js`, `.tsx`, `.jsx`, `.pdf`, `.docx`, `.json`, `.csv`

**Upload a file:**

```bash
curl -s -X POST http://localhost:8802/v1/files \
  -F "file=@document.pdf"
```

**Response (201):**

```json
{
  "id": "file-...",
  "object": "file",
  "filename": "document.pdf",
  "bytes": 204800,
  "created_at": 1741564800,
  "purpose": "assistants",
  "status": "uploaded"
}
```

**List files:**

```bash
curl -s http://localhost:8802/v1/files
```

**Get file metadata:**

```bash
curl -s http://localhost:8802/v1/files/file-abc123
```

**Download file content:**

```bash
curl -s http://localhost:8802/v1/files/file-abc123/content -o output.pdf
```

**Delete a file:**

```bash
curl -s -X DELETE http://localhost:8802/v1/files/file-abc123
```

***

### GET /health

Shallow liveness probe. Returns immediately without calling dependencies.

```bash
curl -s http://localhost:8802/health
```

```json
{"status": "ok", "version": "0.1.0"}
```

Returns `503` with `{"status": "starting"}` while NATS is not yet connected.

***

### GET /health/deep

Readiness probe. Checks PostgreSQL and NATS connectivity; also checks MinIO when RAG is enabled.

```bash
curl -s http://localhost:8802/health/deep
```

```json
{
  "status": "ok",
  "version": "0.1.0",
  "components": {
    "postgres": true,
    "nats": true
  }
}
```

Returns `503` if any component is unhealthy.

***

## NATS Async Interface

Sherlock subscribes to multiple NATS subjects for async reasoning. Clients that cannot use HTTP can publish to these subjects directly.

| Subject | Direction | Description |
|---------|-----------|-------------|
| `arc.reasoner.request` | subscribe | Incoming reasoning requests (primary arc.\* path) |
| `reasoner.request` | subscribe | Legacy request subject (backward compat) |
| `reasoner.v1.chat` | subscribe | OpenAI ChatCompletionRequest wire format |
| `arc.reasoner.stream.{request_id}` | publish | Token chunks as they stream from the LLM |
| `arc.reasoner.result` | publish | Completion signal after stream ends |
| `arc.reasoner.error` | publish | Error payloads for failed requests |
| `arc.reasoner.guard.rejected` | publish | Requests blocked by injection guard |
| `arc.reasoner.guard.intercepted` | publish | Requests with suspicious output intercepted |
| `arc.reasoner.requests.durable` | publish | NATS JetStream durable subject |
| `arc.reasoner.requests.failed` | publish | Dead-letter queue for unprocessable messages |

**Request payload (arc.reasoner.request):**

```json
{
  "request_id": "req-uuid",
  "user_id": "user-uuid",
  "text": "What is the capital of France?"
}
```

**Stream chunk (arc.reasoner.stream.{request\_id}):**

```json
{"token": "Paris", "request_id": "req-uuid"}
```

**Completion (arc.reasoner.result):**

```json
{
  "request_id": "req-uuid",
  "user_id": "user-uuid",
  "text": "Paris.",
  "latency_ms": 312
}
```
