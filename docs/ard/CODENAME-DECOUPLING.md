# Feature: decouple-service-codenames

> **Status: Implemented** — spec `specs/014-decouple-service-codenames/` (branch `014-decouple-service-codenames`)

> Spec folder: `specs/014-decouple-service-codenames/`

## Problem

Codenames (Sherlock, Flash, Sonic, Oracle, etc.) are a fun-factor identifier — they must NOT be coupled into source code, wire protocols, or config defaults. Currently they leak into four tiers of coupling.

## Scope — What Changes

### Tier 1 — Python Package Name (Deepest)
The entire reasoner service lives under `src/sherlock/`. Every internal import is `from sherlock.xxx import ...`.

| What | Current | Target |
|------|---------|--------|
| Python package directory | `services/reasoner/src/sherlock/` | `services/reasoner/src/reasoner/` |
| All internal imports | `from sherlock.xxx import` | `from reasoner.xxx import` |
| Dockerfile CMD / entrypoint | references `sherlock` module | references `reasoner` module |
| `pyproject.toml` package name | `arc-sherlock` | `arc-reasoner` |

### Tier 2 — Wire Protocol (NATS Subjects + Pulsar Topics + DB Schema)
Public-facing contracts. Any external subscriber breaks without a migration period.

| What | Current | Target |
|------|---------|--------|
| NATS legacy subject | `sherlock.request` | `reasoner.request` |
| NATS v1 chat | `sherlock.v1.chat` | `reasoner.v1.chat` |
| NATS v1 result | `sherlock.v1.result` | `reasoner.v1.result` |
| NATS RAG subjects | `sherlock.v1.rag.*` | `reasoner.v1.rag.*` |
| Pulsar request topic | `sherlock-requests` | `reasoner-requests` |
| Pulsar result topic | `sherlock-results` | `reasoner-results` |
| Postgres schema | `sherlock.vector_stores` | `reasoner.vector_stores` |

**Migration strategy:** support both old + new subjects for one release cycle, then drop old.

### Tier 3 — Config Defaults in Go (Cortex)
Cortex hardcodes codename-based DNS hostnames in defaults.

| File | What | Current | Target |
|------|------|---------|--------|
| `services/cortex/internal/config/config.go:108` | Postgres host | `arc-oracle` | `arc-persistence` |
| `services/cortex/internal/config/config.go:116` | NATS URL | `nats://arc-flash:4222` | `nats://arc-messaging:4222` |
| `services/cortex/internal/config/config.go:122` | Redis host | `arc-sonic` | `arc-cache` |
| `services/cortex/internal/clients/postgres.go:16` | probe name | `arc-oracle` | `arc-persistence` |
| `services/cortex/internal/clients/nats.go:16` | probe name | `arc-flash` | `arc-messaging` |
| `services/cortex/internal/clients/redis.go:16` | probe name | `arc-sonic` | `arc-cache` |

Note: Docker container names in compose already use functional names (`arc-messaging`, `arc-cache`, `arc-persistence`). Cortex defaults just need to match.

### Tier 4 — Observability Names
| What | Current | Target |
|------|---------|--------|
| OTEL meter name | `arc-sherlock` | `arc-reasoner` |
| OTEL tracer service name | `arc-sherlock` | `arc-reasoner` |
| `config.py` `service_name` default | `arc-sherlock` | `arc-reasoner` |

## What Does NOT Change
- `service.yaml` `codename:` field — it's metadata, not code
- Docker volume names (`flash-jetstream`, `strange-data`) — internal to compose, not referenced in app code
- `arc-friday-collector` DNS — OTEL collector is a proper name, not a codename reference in logic
- Go module path `arc-framework/cortex` — `cortex` is a functional name (bootstrap orchestrator)
- CLI probe display names that show codenames to users — that's the fun-factor working as intended

## Key Files
```
services/reasoner/src/sherlock/           # entire package to rename
services/reasoner/src/sherlock/config.py  # NATS/Pulsar subjects, service_name
services/reasoner/src/sherlock/nats_handler.py
services/reasoner/src/sherlock/openai_nats_handler.py
services/reasoner/src/sherlock/pulsar_handler.py
services/reasoner/src/sherlock/observability.py
services/reasoner/src/sherlock/memory.py  # schema references
services/reasoner/contracts/asyncapi.yaml # subject definitions
services/cortex/internal/config/config.go
services/cortex/internal/clients/postgres.go
services/cortex/internal/clients/nats.go
services/cortex/internal/clients/redis.go
```

## Risks
- NATS subject rename is a breaking change for any subscriber — needs migration window
- Python package rename requires touching every file in the package (100+ imports)
- DB schema rename requires a migration SQL script
- Cortex hostname defaults must match docker-compose container names exactly
