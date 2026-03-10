# A.R.C. Service Map

Primary naming now follows the operational sources of truth:

1. Root [Makefile](Makefile) target names for orchestration
2. `service.yaml` `name` fields for runtime identity
3. GHCR image names for build and deploy artifacts
4. `codename` as optional metadata only

Do not treat codenames as canonical service identifiers.

## Naming Rules

- Use `make <service>-help` targets as the operator-facing service keys.
- Use `arc-*` names when referring to running services and images.
- Use service directory names under `services/` for implementation location.
- Use codenames only as secondary documentation flavor.

## Authoritative Service Map

Derived from [Makefile](Makefile) includes and `services/*/service.yaml`.

| Make target        | Runtime service        | Image                                               | Path                    | Technology            | Port(s)          | Tier(s)                       | Notes                                         | Codename         |
| ------------------ | ---------------------- | --------------------------------------------------- | ----------------------- | --------------------- | ---------------- | ----------------------------- | --------------------------------------------- | ---------------- |
| `gateway`          | `arc-gateway`          | `ghcr.io/arc-framework/arc-gateway:latest`          | `services/gateway/`     | Traefik               | 80, 8090         | think, reason, ultra-instinct | API gateway and ingress                       | Heimdall         |
| `flags`            | `arc-flags`            | `ghcr.io/arc-framework/arc-flags:latest`            | `services/flags/`       | Unleash               | 4242             | ultra-instinct (security cap) | Feature flags service                         | Mystique         |
| `vault`            | `arc-vault`            | `ghcr.io/arc-framework/arc-vault:latest`            | `services/secrets/`     | OpenBao               | 8200             | ultra-instinct (security cap) | Secrets management                            | Nick Fury        |
| `messaging`        | `arc-messaging`        | `ghcr.io/arc-framework/arc-messaging:latest`        | `services/messaging/`   | NATS                  | 4222, 8222       | think, reason, ultra-instinct | Low-latency messaging backbone (core)         | Flash            |
| `streaming`        | `arc-streaming`        | `ghcr.io/arc-framework/arc-streaming:latest`        | `services/streaming/`   | Pulsar                | 6650, 8082       | think, reason, ultra-instinct | Durable event streaming (core)                | Strange          |
| `cache`            | `arc-cache`            | `ghcr.io/arc-framework/arc-cache:latest`            | `services/cache/`       | Redis                 | 6379             | think, reason, ultra-instinct | Cache and hot state (core)                    | Sonic            |
| `persistence`      | `arc-persistence`      | `ghcr.io/arc-framework/arc-persistence:latest`      | `services/persistence/` | PostgreSQL + pgvector | 5432             | think, reason, ultra-instinct | Long-term state and SQL storage (core)        | Oracle           |
| `storage`          | `arc-storage`          | `ghcr.io/arc-framework/arc-storage:latest`          | `services/storage/`     | MinIO                 | 9000, 9001       | ultra-instinct (storage cap)  | Object storage                                | Tardis           |
| `realtime`         | `arc-realtime`         | `ghcr.io/arc-framework/arc-realtime:latest`         | `services/realtime/`    | LiveKit               | 7880, 7881, 7882 | ultra-instinct (voice cap)    | Realtime media stack; includes sidecars below | Daredevil        |
| `reasoner`         | `arc-reasoner`         | `ghcr.io/arc-framework/arc-reasoner:latest`         | `services/reasoner/`    | FastAPI + LangGraph   | 8802             | reason, ultra-instinct        | Reasoning engine (reasoner cap)               | Sherlock         |
| `cortex`           | `arc-cortex`           | `ghcr.io/arc-framework/arc-cortex:latest`           | `services/cortex/`      | Go                    | 8801             | think, reason, ultra-instinct | Bootstrap/orchestration service (core)        | Cortex           |
| `otel`             | `arc-friday`           | `ghcr.io/arc-framework/arc-friday:latest`           | `services/otel/`        | SigNoz stack          | 3301, 8080       | ultra-instinct (observe cap) † | Full observability stack                      | Friday           |
| `friday-collector` | `arc-friday-collector` | `ghcr.io/arc-framework/arc-friday-collector:latest` | `services/otel/`        | OTEL Collector        | 4317 (OTLP gRPC) | think, reason, ultra-instinct | Telemetry collector (core)                    | Friday Collector |

† `otel` SigNoz UI is also available via `make dev PROFILE=observe` (dev-only, not a product tier).

## Realtime Sidecars

`realtime` is the operational unit exposed by [Makefile](Makefile), but it includes additional runtime services defined in [services/realtime/service.yaml](services/realtime/service.yaml):

| Runtime service        | Image                                               | Purpose              | Codename |
| ---------------------- | --------------------------------------------------- | -------------------- | -------- |
| `arc-realtime-ingress` | `ghcr.io/arc-framework/arc-realtime-ingress:latest` | RTMP ingest          | Sentry   |
| `arc-realtime-egress`  | `ghcr.io/arc-framework/arc-realtime-egress:latest`  | Recording and export | Scribe   |

## Planned Services Not Yet in Makefile

These were left out of the authoritative map on purpose because they do not yet exist as active Make targets or `services/*/service.yaml` entries.

They still matter, so they are tracked separately here as planned services.

| Planned runtime name | Expected role                      | Source of intent                                                                                                                                         | Current status | Notes                                                                   |
| -------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | ----------------------------------------------------------------------- |
| `arc-voice-agent`    | Voice orchestration service        | [docs/ard/VOICE-SYSTEM.md](docs/ard/VOICE-SYSTEM.md), [specs/016-voice-system/spec.md](specs/016-voice-system/spec.md)                                   | In development | Port 8803; `services/voice/` exists; Make targets wired; pending Makefile registration |
| `arc-guard`          | Guardrails / policy enforcement    | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Referenced by nervous system; not yet present in `services/`            |
| `arc-critic`         | Response evaluation / critique     | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Async consumer of reasoning events                                      |
| `arc-gym`            | Training / reinforcement signals   | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Async training loop service                                             |
| `arc-billing`        | Usage metering and cost tracking   | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Reads token usage events                                                |
| `arc-db-vector`      | Dedicated vector retrieval service | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Mentioned in architecture; not currently a concrete service directory   |
| `arc-identity`       | Identity and authentication        | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md)                                                                       | Planned        | Mentioned in framework service reference; not present in Makefile       |
| `arc-chaos`          | Chaos and resilience testing       | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md)                                                                       | Planned        | Target service for resilience stage, not yet implemented in `services/` |

### Why these are separated

- **Authoritative map** = what operators can run today from [Makefile](Makefile)
- **Planned services** = what architecture and specs say will exist, but is not runnable yet

This avoids mixing deployed reality with roadmap intent.

## Composite and Utility Targets

These are not standalone runtime services, but they are included by the root [Makefile](Makefile) as orchestration helpers:

| Target group              | Source                  | Purpose                                |
| ------------------------- | ----------------------- | -------------------------------------- |
| `dev-*`                   | [Makefile](Makefile)    | Profile startup, health, logs, cleanup |
| `data-*`                  | `services/data.mk`      | Aggregate data-layer workflows         |
| `control-*`               | `services/control.mk`   | Aggregate control-plane workflows      |
| `messaging-*`             | `services/messaging.mk` | Aggregate fast-path infra helpers      |
| `scripts-*` / `publish-*` | `scripts/scripts.mk`    | Build, publish, and support tasks      |

## Usage Examples

- `make reasoner-help`
- `make realtime-up`
- `make messaging-health`
- `make dev PROFILE=reason`

## Preferred References

Use these forms in docs and specs:

- `arc-reasoner`
- `arc-messaging`
- `arc-streaming`
- `arc-cache`
- `arc-persistence`
- `arc-realtime`

Avoid codename-first references in architecture, contracts, config defaults, and service maps.

## Python Service Ports (Async Interfaces)

Python services expose their internal contracts as `runtime_checkable` Protocol classes. These are the stable boundaries between adapters and the service core.

### arc-reasoner (`services/reasoner/src/reasoner/interfaces.py`)

```python
class LLMProviderPort(Protocol):
    """Factory — returns a configured LangChain BaseChatModel."""
    def create_llm(self) -> BaseChatModel: ...
    def supports_system_role(self) -> bool: ...
    def provider_name(self) -> str: ...

class ChatCompletionPort(Protocol):
    """Backs POST /v1/chat/completions (non-streaming)."""
    async def complete(self, req: ChatCompletionRequest) -> ChatCompletionResponse: ...

class StreamingPort(Protocol):
    """Backs POST /v1/chat/completions with stream=true."""
    def stream(self, req: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]: ...

class ModelRegistryPort(Protocol):
    """Backs GET /v1/models."""
    def list_models(self) -> ModelList: ...
    def model_exists(self, model_id: str) -> bool: ...

class ResponsesPort(Protocol):
    """Backs POST /v1/responses."""
    async def respond(self, req: ResponsesRequest) -> ResponsesResponse: ...

class OpenAINATSPort(Protocol):
    """NATS v1 chat handler — subscribes to reasoner.v1.chat."""
    async def connect(self) -> None: ...
    async def subscribe(self) -> None: ...
    def is_connected(self) -> bool: ...
    async def close(self) -> None: ...
```

### arc-voice-agent (`services/voice/src/voice/interfaces.py`)

```python
class STTPort(Protocol):
    """Speech-to-text. Concrete: WhisperSTTAdapter (faster-whisper)."""
    async def transcribe(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptResult: ...
    # TranscriptResult(text: str, language: str, duration_secs: float)

class TTSPort(Protocol):
    """Text-to-speech. Concrete: PiperTTSAdapter (piper subprocess)."""
    async def synthesize(self, text: str, voice: str) -> SynthesisResult: ...
    # SynthesisResult(wav_bytes: bytes, sample_rate: int, duration_secs: float)

class LLMBridgePort(Protocol):
    """Reasoning bridge. Concrete: NATSBridge (request-reply to arc-reasoner)."""
    async def reason(
        self, transcript: str, session_id: str, correlation_id: str
    ) -> str: ...
    # Raises: BridgeError(is_timeout: bool, error_type: str)
```

Full command reference for all services: [docs/ard/SERVICE-COMMANDS.md](docs/ard/SERVICE-COMMANDS.md)
CLI tier alignment + workspace init rewrite: [docs/ard/CLI-PLATFORM-INTEGRATION.md](docs/ard/CLI-PLATFORM-INTEGRATION.md)

## CLI Service Catalog Entries (Source of Truth)

This section is the authoritative source for `arc-framework/arc-cli/pkg/catalog/data/services.yaml`.

The CLI catalog has drifted from the platform. Copy these entries verbatim to update the catalog. Dependency names reference other catalog codenames (not Make targets or runtime service names).

**How CLI triggers services:**
`arc workspace run` reads `arc.yaml` → maps `tier` → resolves services from embedded `profiles.yaml` → renders docker-compose from service catalog entries → calls `docker compose up`.

**Command translation:**

| CLI command | Platform equivalent |
|-------------|---------------------|
| `arc workspace init --tier think` | sets up arc.yaml with `tier: think` |
| `arc workspace run` | `make dev PROFILE=<tier>` (effectively) |
| `arc services list` | lists catalog entries (not running containers) |
| `arc services info <codename>` | shows service metadata from catalog |
| `arc services ports <codename>` | shows port mappings from catalog |

```yaml
# ─── Infrastructure ───────────────────────────────────────────────────────────

gateway:
  codename: gateway
  technology: Traefik
  role: Infrastructure
  description: "API gateway and ingress. Routes all inbound HTTP and WebSocket traffic."
  version: "3.0"
  image: "traefik:v3.0"
  arc_image: "arc-gateway"
  released: true
  ports:
    - host: 80
      container: 80
      protocol: tcp
      description: "HTTP traffic"
    - host: 8090
      container: 8080
      protocol: tcp
      description: "Traefik dashboard"
  aliases:
    - traefik
    - heimdall

messaging:
  codename: messaging
  technology: NATS
  role: Infrastructure
  description: "Low-latency messaging backbone for agent-to-service communication."
  version: "latest"
  arc_image: "arc-messaging"
  released: true
  ports:
    - host: 4222
      container: 4222
      protocol: tcp
      description: "Client connections"
    - host: 8222
      container: 8222
      protocol: tcp
      description: "HTTP monitoring"
  aliases:
    - nats
    - flash

streaming:
  codename: streaming
  technology: Apache Pulsar
  role: Infrastructure
  description: "Durable event streaming for high-throughput async event flows."
  version: "latest"
  arc_image: "arc-streaming"
  released: true
  ports:
    - host: 6650
      container: 6650
      protocol: tcp
      description: "Pulsar broker"
    - host: 8082
      container: 8080
      protocol: tcp
      description: "Pulsar admin API"
  aliases:
    - pulsar
    - strange

cache:
  codename: cache
  technology: Redis
  role: Infrastructure
  description: "Cache and hot state layer."
  version: "latest"
  arc_image: "arc-cache"
  released: true
  ports:
    - host: 6379
      container: 6379
      protocol: tcp
      description: "Redis"
  aliases:
    - redis
    - sonic

persistence:
  codename: persistence
  technology: PostgreSQL 17 + pgvector
  role: Infrastructure
  description: "Long-term relational storage with vector search extension."
  version: "17"
  arc_image: "arc-persistence"
  released: true
  ports:
    - host: 5432
      container: 5432
      protocol: tcp
      description: "PostgreSQL"
  aliases:
    - postgres
    - oracle

storage:
  codename: storage
  technology: MinIO
  role: Infrastructure
  description: "S3-compatible object storage for files, models, and media."
  version: "latest"
  arc_image: "arc-storage"
  released: true
  ports:
    - host: 9000
      container: 9000
      protocol: tcp
      description: "MinIO API"
    - host: 9001
      container: 9001
      protocol: tcp
      description: "MinIO console"
  aliases:
    - minio
    - tardis

vault:
  codename: vault
  technology: OpenBao
  role: Infrastructure
  description: "Secrets management."
  version: "latest"
  arc_image: "arc-vault"
  released: true
  ports:
    - host: 8200
      container: 8200
      protocol: tcp
      description: "Vault API"
  aliases:
    - secrets
    - nick-fury

flags:
  codename: flags
  technology: Unleash
  role: Infrastructure
  description: "Feature flag service."
  version: "latest"
  arc_image: "arc-flags"
  released: true
  ports:
    - host: 4242
      container: 4242
      protocol: tcp
      description: "Unleash API"
  aliases:
    - unleash
    - mystique

# ─── Observability ────────────────────────────────────────────────────────────

friday-collector:
  codename: friday-collector
  technology: OTEL Collector
  role: Infrastructure
  description: "OpenTelemetry collector — receives traces, metrics, logs from all services."
  arc_image: "arc-friday-collector"
  released: true
  ports:
    - host: 4317
      container: 4317
      protocol: tcp
      description: "OTLP gRPC receiver"
  aliases:
    - otel-collector

otel:
  codename: otel
  technology: SigNoz + ClickHouse
  role: Infrastructure
  description: "Full observability stack — traces, metrics, logs UI."
  arc_image: "arc-friday"
  released: true
  dependencies:
    - friday-collector
  ports:
    - host: 3301
      container: 3301
      protocol: tcp
      description: "SigNoz UI"
    - host: 8080
      container: 8080
      protocol: tcp
      description: "SigNoz API"
  aliases:
    - signoz
    - friday

# ─── Platform Services ────────────────────────────────────────────────────────

cortex:
  codename: cortex
  technology: Go
  role: Service
  description: "Bootstrap and orchestration service. Initialises platform state on startup."
  arc_image: "arc-cortex"
  released: true
  ports:
    - host: 8801
      container: 8801
      protocol: tcp
      description: "Cortex health + control API"
  dependencies:
    - persistence
    - messaging

reasoner:
  codename: reasoner
  technology: FastAPI + LangGraph
  role: Service
  description: "Central reasoning engine. OpenAI-compatible API backed by LangGraph."
  arc_image: "arc-reasoner"
  released: true
  ports:
    - host: 8802
      container: 8802
      protocol: tcp
      description: "Reasoner API (/v1/chat/completions, /v1/models, /health)"
  dependencies:
    - persistence
    - messaging
    - streaming
    - friday-collector
  environment:
    - name: LLM_PROVIDER
      default: "openai"
      required: false
      description: "LLM provider (openai, anthropic, ollama)"
    - name: LLM_MODEL
      default: "gpt-4o"
      required: false
      description: "Model identifier"
    - name: LLM_API_KEY
      required: true
      description: "Provider API key"
  aliases:
    - sherlock
    - brain
    - agent

# ─── Realtime ─────────────────────────────────────────────────────────────────

realtime:
  codename: realtime
  technology: LiveKit Server
  role: Service
  description: "Realtime media stack — WebRTC rooms for voice and video."
  arc_image: "arc-realtime"
  released: true
  ports:
    - host: 7880
      container: 7880
      protocol: tcp
      description: "LiveKit HTTP API"
    - host: 7881
      container: 7881
      protocol: tcp
      description: "LiveKit gRPC"
    - host: 7882
      container: 7882
      protocol: tcp
      description: "LiveKit RTC (TCP fallback)"
    - host: 50100
      container: 50100
      protocol: udp
      description: "WebRTC media (UDP range start)"
  aliases:
    - livekit
    - daredevil

# ─── Voice ────────────────────────────────────────────────────────────────────

voice:
  codename: voice
  technology: FastAPI + LiveKit Agents
  role: Service
  description: "Voice agent — STT (Whisper), TTS (Piper), LLM bridge to reasoner via NATS."
  arc_image: "arc-voice-agent"
  released: false                   # pending Makefile registration
  ports:
    - host: 8803
      container: 8803
      protocol: tcp
      description: "Voice API (/v1/audio/transcriptions, /v1/audio/speech, /health)"
  dependencies:
    - messaging
    - streaming
    - realtime
    - friday-collector
    - cache
    - reasoner
  environment:
    - name: WHISPER_MODEL
      default: "tiny"
      required: false
      description: "Whisper model size (tiny, base, small, medium, large)"
    - name: PIPER_BIN
      default: "/usr/local/bin/piper"
      required: false
      description: "Path to piper TTS binary"
    - name: BRIDGE_NATS_SUBJECT
      default: "arc.reasoner.request"
      required: false
      description: "NATS subject for LLM bridge requests"
  aliases:
    - scarlett
    - voice-agent
```
