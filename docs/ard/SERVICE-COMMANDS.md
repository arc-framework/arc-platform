# A.R.C. Service Command Reference

> Operator reference for all platform services — ports, health endpoints, make targets, and async interfaces.
>
> **Tiers:** `think` | `reason` | `ultra-instinct`
> **Dev-only profile:** `observe` (think + SigNoz UI, not a tier)
> **Root command:** `make dev [PROFILE=<tier>]`

---

## Infrastructure Services

### gateway (`arc-gateway`)

| Field | Value |
|-------|-------|
| Technology | Traefik v3 |
| Port | `80` (HTTP), `8090` (dashboard) |
| Health | `http://localhost:8090/ping` |
| Tiers | think, reason, ultra-instinct |

```bash
make gateway-up           # start container
make gateway-down         # stop container
make gateway-health       # check health
make gateway-logs         # tail logs
make gateway-nuke         # remove container + image
```

---

### messaging (`arc-messaging`)

| Field | Value |
|-------|-------|
| Technology | NATS |
| Ports | `4222` (client), `8222` (monitoring) |
| Health | `http://localhost:8222/healthz` |
| Tiers | think, reason, ultra-instinct |

```bash
make messaging-up
make messaging-down
make messaging-health
make messaging-logs
make messaging-nuke
```

---

### streaming (`arc-streaming`)

| Field | Value |
|-------|-------|
| Technology | Apache Pulsar |
| Ports | `6650` (broker), `8082` (admin) |
| Health | `http://localhost:8082/admin/v2/brokers/health` |
| Tiers | think, reason, ultra-instinct |
| Note | Cold start ~90 s; `streaming-up` waits up to 120 s |

```bash
make streaming-up
make streaming-down
make streaming-health
make streaming-logs
make streaming-clean      # interactive confirmation required
make streaming-nuke       # interactive confirmation required
```

---

### cache (`arc-cache`)

| Field | Value |
|-------|-------|
| Technology | Redis |
| Port | `6379` |
| Health | `docker exec arc-cache redis-cli ping` |
| Tiers | think, reason, ultra-instinct |

```bash
make cache-up
make cache-down
make cache-health
make cache-logs
make cache-nuke
```

---

### persistence (`arc-persistence`)

| Field | Value |
|-------|-------|
| Technology | PostgreSQL 17 + pgvector |
| Port | `5432` |
| Health | `docker exec arc-persistence pg_isready -U arc` |
| Tiers | think, reason, ultra-instinct |

```bash
make persistence-up
make persistence-down
make persistence-health
make persistence-logs
make persistence-nuke
```

---

### storage (`arc-storage`)

| Field | Value |
|-------|-------|
| Technology | MinIO |
| Ports | `9000` (API), `9001` (console) |
| Health | `http://localhost:9000/minio/health/live` |
| Tiers | reason, ultra-instinct |

```bash
make storage-up
make storage-down
make storage-health
make storage-logs
make storage-nuke
```

---

### secrets (`arc-vault`)

| Field | Value |
|-------|-------|
| Technology | OpenBao |
| Port | `8200` |
| Health | `http://localhost:8200/v1/sys/health` |
| Tiers | reason, ultra-instinct |

```bash
make vault-up
make vault-down
make vault-health
make vault-logs
make vault-nuke
```

---

### flags (`arc-flags`)

| Field | Value |
|-------|-------|
| Technology | Unleash |
| Port | `4242` |
| Health | `http://localhost:4242/health` |
| Tiers | reason, ultra-instinct |

```bash
make flags-up
make flags-down
make flags-health
make flags-logs
make flags-nuke
```

---

### otel (`arc-friday`)

| Field | Value |
|-------|-------|
| Technology | SigNoz + ClickHouse |
| Ports | `3301` (UI), `8080` (API), `4317` (OTLP gRPC via friday-collector) |
| Health | `http://localhost:3301/api/v1/health` |
| Tiers | reason, ultra-instinct |
| Dev profile | `observe` (think + otel only) |

```bash
make otel-up
make otel-down
make otel-health
make otel-logs
make otel-nuke
```

---

### realtime (`arc-realtime`)

| Field | Value |
|-------|-------|
| Technology | LiveKit Server |
| Ports | `7880` (HTTP), `7881` (gRPC), `7882` (TCP), `50100–50200` (UDP) |
| Health | `http://localhost:7880` |
| Tiers | reason, ultra-instinct |
| Sidecars | `arc-realtime-ingress` (:7888), `arc-realtime-egress` (:7889) |

```bash
make realtime-up
make realtime-down
make realtime-health
make realtime-logs
make realtime-nuke
```

---

## Platform Services

### cortex (`arc-cortex`)

| Field | Value |
|-------|-------|
| Technology | Go |
| Port | `8801` |
| Health | `http://localhost:8801/health` |
| Tiers | think, reason, ultra-instinct (implicit dependency) |

```bash
make cortex-up
make cortex-down
make cortex-health
make cortex-logs
make cortex-build         # compile Docker image
make cortex-bin           # compile local binary
make cortex-run           # run locally against localhost infra
make cortex-run-dev       # run locally with OTEL enabled
make cortex-test          # go test ./...
make cortex-lint          # golangci-lint
make cortex-nuke
```

---

### reasoner (`arc-reasoner`)

| Field | Value |
|-------|-------|
| Technology | Python — FastAPI + LangGraph |
| Port | `8802` |
| Health | `http://localhost:8802/health` |
| Deep health | `http://localhost:8802/health/deep` |
| Tiers | think, reason, ultra-instinct |
| Dependencies | persistence, messaging, streaming, friday-collector |
| Startup timeout | 180 s (model download on first cold start) |

```bash
make reasoner-up
make reasoner-down
make reasoner-health
make reasoner-logs
make reasoner-build
make reasoner-build-fresh
make reasoner-test         # uv run pytest
make reasoner-test-cover   # pytest + coverage
make reasoner-lint         # ruff + mypy
make reasoner-check        # test + lint (mirrors CI)
make reasoner-nuke
```

**HTTP API — OpenAI-compatible endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | Chat completion (streaming: `"stream": true`) |
| `GET`  | `/v1/models` | List available models |
| `POST` | `/v1/responses` | Responses API |
| `POST` | `/v1/embeddings` | Text embeddings (RAG only) |
| `POST` | `/v1/files` | Upload file for RAG |
| `GET`  | `/v1/files` | List files |
| `GET`  | `/v1/files/{id}` | Get file metadata |
| `GET`  | `/v1/files/{id}/content` | Stream file content |
| `DELETE`| `/v1/files/{id}` | Delete file |
| `POST` | `/v1/vector_stores` | Create vector store |
| `GET`  | `/v1/vector_stores/{id}` | Get vector store |
| `POST` | `/v1/vector_stores/{id}/files` | Ingest files (async; `?sync=true` available) |
| `POST` | `/v1/vector_stores/{id}/search` | Search vector store |
| `GET`  | `/health` | Shallow health (always 200) |
| `GET`  | `/health/deep` | Deep health (checks postgres, nats, minio) |

**Async port interfaces** (`services/reasoner/src/reasoner/interfaces.py`):

```python
class LLMProviderPort(Protocol):
    def create_llm(self) -> BaseChatModel: ...
    def supports_system_role(self) -> bool: ...
    def provider_name(self) -> str: ...

class ChatCompletionPort(Protocol):
    async def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse: ...

class StreamingPort(Protocol):
    def stream(self, req: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]: ...

class ModelRegistryPort(Protocol):
    def list_models(self) -> ModelList: ...
    def model_exists(self, model_id: str) -> bool: ...

class ResponsesPort(Protocol):
    async def respond(self, req: ResponsesRequest) -> ResponsesResponse: ...

class OpenAINATSPort(Protocol):
    async def connect(self) -> None: ...
    async def subscribe(self) -> None: ...
    def is_connected(self) -> bool: ...
    async def close(self) -> None: ...
```

---

### voice (`arc-voice-agent`)

| Field | Value |
|-------|-------|
| Technology | Python — FastAPI + LiveKit Agents |
| Port | `8803` |
| Health | `http://localhost:8803/health` |
| Deep health | `http://localhost:8803/health/deep` |
| Tiers | reason, ultra-instinct |
| Dependencies | messaging, streaming, realtime, friday-collector, cache |
| Startup timeout | 60 s |

```bash
make voice-up
make voice-down
make voice-health
make voice-logs
make voice-build
make voice-build-fresh
make voice-test            # uv run pytest
make voice-test-cover      # pytest + coverage
make voice-lint            # ruff + mypy
make voice-check           # test + lint (mirrors CI)
make voice-nuke
```

**HTTP API:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/audio/transcriptions` | Transcribe audio file (STT) — multipart `file` field |
| `POST` | `/v1/audio/speech` | Synthesize text to WAV (TTS) — JSON body |
| `GET`  | `/health` | Shallow health (always 200) |
| `GET`  | `/health/deep` | Deep health (checks arc-realtime + arc-messaging) |

**Async port interfaces** (`services/voice/src/voice/interfaces.py`):

```python
class STTPort(Protocol):
    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptResult: ...
    # TranscriptResult: text, language, duration_secs

class TTSPort(Protocol):
    async def synthesize(self, text: str, voice: str) -> SynthesisResult: ...
    # SynthesisResult: wav_bytes, sample_rate, duration_secs

class LLMBridgePort(Protocol):
    async def reason(
        self, transcript: str, session_id: str, correlation_id: str
    ) -> str: ...
    # Raises: BridgeError(is_timeout, error_type)
```

**Concrete adapters:**

| Port | Adapter | Implementation |
|------|---------|----------------|
| `STTPort` | `WhisperSTTAdapter` | faster-whisper, runs in thread-pool executor |
| `TTSPort` | `PiperTTSAdapter` | piper binary subprocess, runs in thread-pool executor |
| `LLMBridgePort` | `NATSBridge` | NATS request-reply to `arc-reasoner` |

---

## Global Orchestration

```bash
# Start a tier (all services in profile, dependency order)
make dev                         # think profile (default)
make dev PROFILE=observe         # think + SigNoz (dev only)
make dev PROFILE=reason          # full dev stack
make dev PROFILE=ultra-instinct  # everything

# Control
make dev-down          # stop all profile services
make dev-health        # check health of all profile services
make dev-logs          # tail logs from all profile services
make dev-status        # container status table
make dev-images        # check / pull images for profile

# Destructive (confirm before running)
make dev-clean         # remove containers + volumes
make dev-nuke          # remove containers + volumes + images

# Utilities
make help              # list all targets
make scrub             # clean all build caches (Python, Go, Node, Make)
make dev-regen         # force regenerate .make/ profile + registry metadata
make otel-up           # OTEL collector + SigNoz stack (alias for otel targets)
```
