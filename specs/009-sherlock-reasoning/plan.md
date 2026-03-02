# Implementation Plan: Sherlock Reasoning Service

> **Spec**: 009-sherlock-reasoning
> **Date**: 2026-03-01

## Summary

Sherlock (`arc-sherlock`) is the first Python intelligence service in the arc-platform monorepo — a LangGraph 1.0.x reasoning engine with dual-store memory (Qdrant for semantic ANN, PostgreSQL for ordered history) and three invocation transports: HTTP sync, NATS request-reply, and Pulsar durable async (opt-in). The service is adapted from the POC at `platform-spike/services/arc-sherlock-brain`, replacing pgvector with Qdrant (Cerebro), adding a full test suite, proper OTEL instrumentation, and a multi-stage Alpine Dockerfile targeting `services/reasoner/`.

---

## Target Modules

| Module | Language | Changes |
|--------|----------|---------|
| `services/reasoner/` | Python 3.13 | New — 19 files; full service from scratch |
| `services/profiles.yaml` | YAML | Modify — add `reasoner` to `reason` profile |
| `Makefile` | Make | Modify — add `include services/reasoner/reasoner.mk` |

---

## Technical Context

| Aspect | Value |
|--------|-------|
| Language | Python 3.13 (Alpine, multi-stage) |
| Framework | FastAPI + LangGraph 1.0.x |
| LLM client | `langchain-ollama` — `ChatOllama` |
| Vector store | Qdrant (`qdrant-client>=1.9`, `AsyncQdrantClient`) |
| Relational DB | PostgreSQL (`sqlalchemy>=2.0` async + `asyncpg`) |
| Embeddings | `sentence-transformers>=3.0` — `all-MiniLM-L6-v2`, 384-dim, Cosine |
| Messaging | NATS (`nats-py>=2.9`) — request-reply + fire-and-forget |
| Streaming | Pulsar (`pulsar-client>=3.4`) — durable async, opt-in |
| Config | Pydantic `BaseSettings` — `SHERLOCK_` prefix, 12-Factor |
| Observability | `opentelemetry-*>=1.27` + `structlog>=24.4` |
| Testing | `pytest>=8` + `pytest-asyncio>=0.24` + `httpx>=0.27` (all mocked) |
| Linting | `ruff>=0.6` + `mypy>=1.11` |

**POC delta** (key differences from `platform-spike/services/arc-sherlock-brain`):

| POC | Production |
|-----|------------|
| pgvector in PostgreSQL | Qdrant (Cerebro) — dedicated vector DB |
| `os.getenv()` | `Pydantic BaseSettings` — `SHERLOCK_` prefix |
| `langchain_community.ChatOllama` | `langchain_ollama.ChatOllama` |
| No tests | Full pytest suite, 75% coverage target |
| NATS subject `brain.request` | `sherlock.request` |
| LangGraph `set_entry_point()` | `workflow.add_edge(START, ...)` (1.0.x API) |
| No OTEL | OTEL traces + metrics + structlog |
| Port 8000 | Host port 8083 (cortex=8081, pulsar-admin=8082) |

---

## Architecture

### Component Overview

```mermaid
graph TB
    subgraph Callers
        CLI[CLI / HTTP :8083]
        Scarlett[Scarlett — NATS]
        Batch[Batch Jobs — Pulsar]
    end

    subgraph "services/reasoner — arc-sherlock"
        API["FastAPI\nPOST /chat\nGET /health\nGET /health/deep"]
        NH["NATSHandler\nsherlock.request\nqueue: sherlock_workers"]
        PH["PulsarHandler\nsherlock-requests\nsub: sherlock-workers\nasyncio.to_thread wrapper"]

        subgraph "LangGraph StateGraph"
            ST[START]
            RC[retrieve_context]
            GR[generate_response]
            EH[error_handler]
            EN[END]
            ST --> RC
            RC --> GR
            GR --> EN
            RC -->|exception| EH
            GR -->|exception| EH
            EH -->|retry < 3| GR
            EH --> EN
        end

        subgraph "AppState dataclass"
            AS["memory: SherlockMemory\ngraph: CompiledGraph\nnats: NATSHandler\npulsar: PulsarHandler\nmetrics: SherlockMetrics"]
        end
    end

    subgraph "Platform Dependencies"
        QD[(Cerebro\nQdrant :6333\nsherlock_conversations)]
        PG[(Oracle\nPostgreSQL :5432\nsherlock.conversations)]
        NATS[Flash — NATS :4222]
        Pulsar[Dr. Strange — Pulsar :6650]
        OL[Ollama / vLLM :11434]
        OTEL[Friday Collector :4317]
    end

    CLI --> API
    Scarlett --> NATS --> NH
    Batch --> Pulsar --> PH

    API --> RC
    NH --> RC
    PH --> RC

    RC -->|search| QD
    RC -->|history| PG
    GR -->|ainvoke| OL
    GR -->|save| PG
    GR -->|upsert| QD
    API -.->|traces/metrics| OTEL
```

### Invocation Sequence

```mermaid
sequenceDiagram
    participant C as Caller
    participant S as arc-sherlock
    participant M as SherlockMemory
    participant L as Ollama

    Note over C,S: Mode 1 — HTTP sync
    C->>S: POST /chat {user_id, text}
    S->>M: search(user_id, text) → context
    S->>L: ainvoke(messages + context)
    S->>M: save(user_id, human + ai turns)
    S-->>C: {user_id, text, latency_ms}

    Note over C,S: Mode 2 — NATS request-reply
    C->>S: nc.request("sherlock.request", payload, timeout=30)
    S->>M: search + generate + save
    S-->>C: msg.respond(result) → ephemeral _INBOX

    Note over C,S: Mode 3 — Pulsar durable async (opt-in)
    C->>S: producer.send("sherlock-requests", {request_id,...})
    note right of S: asyncio.to_thread wraps<br/>blocking pulsar-client
    S->>M: search + generate + save
    S->>C: producer.send("sherlock-results", {request_id,...})
    S->>S: consumer.acknowledge(msg)
```

### Memory Architecture

```mermaid
graph LR
    subgraph "Tier 1 — Working Memory (per-invocation)"
        AG[AgentState in LangGraph]
    end
    subgraph "Tier 2 — Semantic Memory"
        QD["Qdrant\ncosine ANN 384-dim\nuser_id filter\ntop-k context"]
    end
    subgraph "Tier 3 — Chronological History"
        PG["PostgreSQL\nsherlock.conversations\nORDER BY created_at"]
    end

    AG -->|encode + search| QD
    QD -->|top-k context strings| AG
    AG -->|persist human+ai turns| PG
    AG -->|upsert vectors| QD
```

---

## Constitution Check

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Zero-Dep CLI | N/A | Service only — no CLI changes |
| II | Platform-in-a-Box | **PASS** | `make reasoner-up` starts service; `reason` profile includes it |
| III | Modular Services | **PASS** | Self-contained `services/reasoner/` with `service.yaml`, own Dockerfile |
| IV | Two-Brain | **PASS** | Python only — intelligence layer; no Go mixed in |
| V | Polyglot Standards | **PASS** | FastAPI + LangGraph, ruff + mypy, pytest, `SHERLOCK_` prefix, structlog |
| VI | Local-First | N/A | CLI principle |
| VII | Observability | **PASS** | `/health` + `/health/deep`, OTEL traces/metrics/structlog, `arc-friday-collector` |
| VIII | Security | **PASS** | Non-root `sherlock:sherlock`, `127.0.0.1:8083` bind, content tracing off by default |
| IX | Declarative | N/A | CLI principle |
| X | Stateful Ops | N/A | CLI principle |
| XI | Resilience | **PASS** | `tenacity` retries on retrieval, Pulsar `negative_acknowledge` on failure, `start_period: 30s` |
| XII | Interactive | N/A | CLI principle |

---

## Project Structure

```
arc-platform/
├── specs/
│   └── 009-sherlock-reasoning/
│       └── contracts/
│           ├── openapi.yaml                # OpenAPI 3.1 — HTTP API contract
│           └── asyncapi.yaml              # AsyncAPI 3.0 — NATS + Pulsar event contracts
│
├── services/
│   ├── reasoner/                           # NEW SERVICE
│   │   ├── Dockerfile                      # multi-stage, python:3.13-alpine, non-root
│   │   ├── docker-compose.yml              # arc-sherlock, port 127.0.0.1:8083:8000
│   │   ├── service.yaml                    # codename: sherlock, role: reasoner
│   │   ├── reasoner.mk                     # make targets following cortex.mk pattern
│   │   ├── pyproject.toml                  # deps: fastapi, langgraph, qdrant-client, nats-py, ...
│   │   └── src/
│   │       └── sherlock/
│   │           ├── __init__.py
│   │           ├── config.py               # Pydantic BaseSettings — SHERLOCK_ prefix
│   │           ├── observability.py        # configure_logging, init_telemetry, SherlockMetrics
│   │           ├── memory.py               # SherlockMemory — Qdrant + PostgreSQL, Conversation ORM
│   │           ├── graph.py                # LangGraph 1.0.x — AgentState, build_graph, invoke_graph
│   │           ├── nats_handler.py         # NATSHandler — queue group sherlock_workers
│   │           ├── pulsar_handler.py       # PulsarHandler — asyncio.to_thread, shared subscription
│   │           └── main.py                 # FastAPI + AppState dataclass + lifespan + /chat + /health*
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py                 # shared fixtures: mock_memory, mock_graph, test_client
│   │       ├── test_api.py                 # /chat, /health, /health/deep — all mocked
│   │       ├── test_graph.py               # build_graph, invoke_graph, error paths
│   │       ├── test_memory.py              # Qdrant upsert/search, PG save, health_check
│   │       ├── test_nats_handler.py        # request-reply, fire-and-forget
│   │       └── test_pulsar_handler.py      # process+ack, failure+nack, asyncio.to_thread
│   │
│   └── profiles.yaml                       # MODIFY — add reasoner to reason profile
│
└── Makefile                                # MODIFY — add include services/reasoner/reasoner.mk
```

**Total new files**: 20 (7 source + 6 tests + 5 infra + `__init__.py` files)
**Modified files**: 2 (`profiles.yaml`, `Makefile`)

---

## Module Designs

### `config.py`

Pydantic `BaseSettings` with `model_config = SettingsConfigDict(env_prefix="SHERLOCK_")` pattern. All fields have sensible defaults pointing at platform service names (e.g. `arc-vector-db`, `arc-messaging`).

Key settings groups:
- **Service**: `service_name`, `service_version`, `host`, `port`
- **LLM**: `llm_model` (default: `mistral:7b`), `llm_base_url`, `embedding_model`, `embedding_dim`, `context_top_k`
- **Qdrant**: `qdrant_host` (`arc-vector-db`), `qdrant_port` (6333), `qdrant_collection` (`sherlock_conversations`)
- **PostgreSQL**: `postgres_url` (`postgresql+asyncpg://arc:arc@arc-sql-db:5432/arc`)
- **NATS**: `nats_url` (`nats://arc-messaging:4222`), `nats_enabled` (True), `nats_subject` (`sherlock.request`), `nats_queue_group` (`sherlock_workers`)
- **Pulsar**: `pulsar_url` (`pulsar://arc-streaming:6650`), `pulsar_enabled` (**False** — opt-in), `pulsar_request_topic`, `pulsar_result_topic`, `pulsar_subscription` (`sherlock-workers`)
- **OTEL**: `otel_endpoint` (`http://arc-friday-collector:4317`) — uses standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var alias; `otel_traces_enabled`, `otel_metrics_enabled`, `content_tracing` (**False** — no prompts/responses in spans)

### `observability.py`

Three exported functions + one class:
- `configure_logging()` — structlog with JSON processors, level from env
- `init_telemetry(settings)` — `TracerProvider` + `MeterProvider`, OTLP gRPC exporters
- `instrument_app(app)` — `FastAPIInstrumentor().instrument_app(app)`
- `SherlockMetrics` — counters: `sherlock.requests.total`, `sherlock.errors.total`; histograms: `sherlock.latency` (ms), `sherlock.context.size`

OTEL span attributes: `user_id`, `transport` (http|nats|pulsar), `latency_ms`. No message content when `content_tracing=False`.

### `memory.py`

`SherlockMemory` class — two async clients:
- **Qdrant** (`AsyncQdrantClient`): `init()` creates collection if absent (vectors `size=384`, distance `Cosine`), `search(user_id, text)` → `list[str]`, `upsert(user_id, role, text)` — both user + AI turns stored with `user_id` payload filter
- **PostgreSQL** (SQLAlchemy async): `init()` creates `sherlock` schema + `sherlock.conversations` table if absent, `save(user_id, role, text)` — INSERT with timestamp, `get_history(user_id, limit)` — ORDER BY created_at

`health_check()` → `{"qdrant": bool, "postgres": bool}` — probes each independently.

`Conversation` ORM model (`sherlock.conversations`):
```
id          UUID primary key
user_id     TEXT NOT NULL (indexed)
role        TEXT NOT NULL  -- "human" | "ai"
content     TEXT NOT NULL
created_at  TIMESTAMPTZ DEFAULT now()
```

Embedding is computed inline via `SentenceTransformer` (loaded once on `SherlockMemory.init()`).

### `graph.py`

LangGraph 1.0.x `StateGraph` with `AgentState` TypedDict:

```python
class AgentState(TypedDict):
    messages:       Annotated[list[BaseMessage], add_messages]
    user_id:        str
    context:        Optional[list[str]]
    final_response: Optional[str]
    error_count:    int
```

Graph edges:
- `START → retrieve_context`
- `retrieve_context → generate_response` (normal)
- `retrieve_context → error_handler` (exception)
- `generate_response → END` (normal)
- `generate_response → error_handler` (exception)
- `error_handler → generate_response` (if `error_count < 3`)
- `error_handler → END` (max retries exhausted — returns error response string)

Nodes capture `memory` and `llm` via closure. `invoke_graph(graph, memory, user_id, text)` is the public function called by all three transports.

### `nats_handler.py`

```python
class NATSHandler:
    async def connect(self) -> None           # nc.connect(settings.nats_url)
    async def subscribe(self) -> None         # nc.subscribe(subject, queue=queue_group, cb=_handle)
    async def _handle(self, msg: Msg) -> None # parse → invoke_graph → msg.respond (if msg.reply)
    async def close(self) -> None
    def is_connected(self) -> bool
```

Fire-and-forget guard: `if msg.reply: await msg.respond(...)` — missing `reply` is silently skipped.

### `pulsar_handler.py`

`pulsar-client` is a synchronous C++ binding — all blocking calls wrapped with `asyncio.to_thread()`. Consumer loop is a background `asyncio.Task` that spawns a sub-task per message (slow inferences don't block the receive loop).

```python
class PulsarHandler:
    async def start(self) -> None    # thread: _connect; task: _consume_loop
    async def close(self) -> None    # cancel task; thread: client.close
    def _connect(self) -> None       # Client + subscribe(Shared) + create_producer
    async def _consume_loop(self) -> None   # background; receive(timeout_millis=5000)
    async def _process(self, msg) -> None   # invoke_graph → send result → ack; on error: nack
```

Pulsar only instantiated when `settings.pulsar_enabled` is `True`.

### `main.py`

```python
@dataclass
class AppState:
    memory:  SherlockMemory
    graph:   CompiledGraph
    nats:    NATSHandler
    pulsar:  Optional[PulsarHandler]
    metrics: SherlockMetrics
```

Lifespan startup order:
1. `configure_logging()`
2. `init_telemetry(settings)`
3. `memory.init()` — creates Qdrant collection + PostgreSQL schema
4. `llm = ChatOllama(model=settings.llm_model, base_url=settings.llm_base_url)`
5. `graph = build_graph(memory, llm)`
6. `nats.connect()` + `nats.subscribe()`
7. `pulsar.start()` — only if `settings.pulsar_enabled`

Endpoints:

| Path | Method | Description |
|------|--------|-------------|
| `/chat` | POST | `{user_id, text}` → `invoke_graph` → `{user_id, text, latency_ms}` |
| `/health` | GET | Shallow — always 200 if NATS connected |
| `/health/deep` | GET | Probes Qdrant + Postgres + NATS → `{status, version, components}` |

---

## Parallel Execution Strategy

```mermaid
gantt
    title Sherlock Implementation Phases
    dateFormat  X
    axisFormat  Phase %s

    section Phase 1 — Foundation
    pyproject.toml + Dockerfile skeleton    :p1a, 0, 1
    config.py (Pydantic BaseSettings)       :p1b, 0, 1

    section Phase 2 — Parallel Core
    observability.py                        :p2a, after p1b, 1
    memory.py (Qdrant + PostgreSQL)         :p2b, after p1b, 2
    nats_handler.py                         :p2c, after p1b, 1

    section Phase 3 — Graph + Pulsar
    graph.py (LangGraph 1.0.x)              :p3a, after p2b, 2
    pulsar_handler.py                       :p3b, after p2c, 1

    section Phase 4 — Integration
    main.py (FastAPI + AppState)            :p4a, after p3a, 1

    section Phase 5 — Tests (parallel)
    conftest.py + test_api.py               :p5a, after p4a, 1
    test_graph.py + test_memory.py          :p5b, after p4a, 1
    test_nats_handler.py + test_pulsar_handler.py :p5c, after p4a, 1

    section Phase 6 — Infra + Wiring
    docker-compose.yml + service.yaml       :p6a, after p4a, 1
    reasoner.mk                             :p6b, after p4a, 1
    Modify profiles.yaml + Makefile         :p6c, after p6a, 1
```

**Parallelism opportunities**:
- Phase 2: `observability.py`, `memory.py`, `nats_handler.py` — all depend only on `config.py` → run concurrently
- Phase 5: All test files can be written concurrently (mock interfaces defined by Phase 4)
- Phase 6: `docker-compose.yml` + `reasoner.mk` can be written concurrently

**Sequential constraints**:
- `graph.py` must wait for `memory.py` (closure captures `SherlockMemory`)
- `main.py` must wait for all modules (ties everything together)
- `profiles.yaml` + `Makefile` modification must wait for `service.yaml` to exist

---

## Infrastructure Files

### `service.yaml`

```yaml
name: arc-sherlock
role: reasoner
codename: sherlock
image: ghcr.io/arc-framework/arc-sherlock:latest
version: "0.1.0"
language: python
port: 8083
health: http://localhost:8083/health
timeout: 180
depends_on:
  - sql-db
  - vector-db
  - messaging
  - streaming
  - friday-collector
```

### `docker-compose.yml`

- Image: `ghcr.io/arc-framework/arc-sherlock:latest`
- Container name: `arc-sherlock`
- Port: `127.0.0.1:8083:8000` (localhost-only)
- Networks: `arc_platform_net` (external), `arc_otel_net` (external)
- Healthcheck: `wget -qO- http://localhost:8000/health || exit 1`, `start_period: 30s`
- No `depends_on` — handled by `resolve-deps.sh` (follows cortex pattern exactly)

### `Dockerfile`

Multi-stage Alpine:
1. **Builder** (`python:3.13-alpine`) — `gcc musl-dev libffi-dev` for C extensions; `pip install --prefix=/install .`
2. **Runtime** (`python:3.13-alpine`) — `libstdc++ libgomp` for PyTorch; non-root `sherlock:sherlock`; copy `/install`; `CMD uvicorn sherlock.main:app`

Fallback: `python:3.13-slim` if Alpine + sentence-transformers fails on arm64.

### `reasoner.mk`

Follows `cortex.mk` pattern exactly — same color macros (`COLOR_INFO/OK/ERR`), same `COMPOSE_VAR` pattern.

Targets: `reasoner-help`, `reasoner-build`, `reasoner-build-fresh`, `reasoner-up`, `reasoner-down`, `reasoner-health`, `reasoner-logs`, `reasoner-test`, `reasoner-test-cover`, `reasoner-lint`, `reasoner-check`, `reasoner-push`, `reasoner-publish`, `reasoner-tag`, `reasoner-clean`, `reasoner-nuke`

---

## Reviewer Checklist

- [ ] All 20 files in `services/reasoner/` created and non-empty
- [ ] `make reasoner-test` passes; `pytest --cov=sherlock` reports ≥ 75% on critical packages
- [ ] `make reasoner-lint` exits 0 — `ruff check src/` and `mypy src/` both clean
- [ ] `make reasoner-build` produces working Docker image (verify with `docker inspect`)
- [ ] `make dev-regen && grep sherlock .make/registry.mk` returns `SERVICE_reasoner_HEALTH` entry
- [ ] `services/profiles.yaml` — `reasoner` present under `reason` profile
- [ ] `Makefile` — `include services/reasoner/reasoner.mk` present after other realtime includes
- [ ] `services/reasoner/service.yaml` — `depends_on` lists `sql-db`, `vector-db`, `messaging`, `streaming`, `friday-collector`
- [ ] `Dockerfile` — `USER sherlock` before `CMD`; non-root enforced
- [ ] `docker-compose.yml` — port binding is `127.0.0.1:8083:8000`; no `depends_on` block
- [ ] No module globals in `main.py` — all singletons live in `AppState` dataclass
- [ ] `PulsarHandler` only instantiated when `settings.pulsar_enabled=True`
- [ ] NATS handler guards `msg.respond()` with `if msg.reply:` check
- [ ] OTEL span attributes contain no message content when `SHERLOCK_CONTENT_TRACING=false`
- [ ] Constitution compliance: II, III, IV, V, VII, VIII, XI all PASS
- [ ] `spec-doc.md` removed from project root
- [ ] `specs/index.md` updated with `009-sherlock-reasoning` entry
- [ ] `contracts/openapi.yaml` schemas match Pydantic models in `main.py`
- [ ] `contracts/asyncapi.yaml` payload schemas match `NATSHandler` + `PulsarHandler` JSON structures

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Alpine + `sentence-transformers` build fails on arm64 | H | Fallback: `python:3.13-slim`; document in Dockerfile comment |
| `pulsar-client` C++ bindings unavailable for target arch | M | Document in `pyproject.toml`; Pulsar is opt-in so service still works without it |
| Ollama not running at startup | M | `ChatOllama` lazy — connection attempted only on first `ainvoke()`; health endpoint stays green |
| Qdrant collection created with wrong dimensions | M | `init()` checks `collection.config.params.vectors.size == embedding_dim`; raises if mismatch |
| LangGraph 1.0.x API breaks from 0.2.x POC | L | Explicitly pinned `langchain-langgraph>=1.0`; `START`/`END`/`add_messages` from `langgraph.graph` |
| `sentence-transformers` download on cold start (90MB) | L | `start_period: 30s` in healthcheck; model cached in Docker layer if baked in |
| Pulsar negative-ack message storm on repeated LLM failures | L | `error_handler` caps retries at 3; returns error payload instead of raising; message acked on error response |
| PostgreSQL `sherlock.conversations` table missing on first run | L | `memory.init()` creates schema + table if absent; idempotent |
