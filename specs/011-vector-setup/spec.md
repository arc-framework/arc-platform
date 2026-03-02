# Feature: pgvector Migration + Observability Hardening

> **Spec**: 011-vector-setup
> **Date**: 2026-03-02
> **Status**: Draft
> **Branch**: 011-vector-setup

## Overview

Replace Qdrant (Cerebro / `arc-vector-db`) with pgvector — a PostgreSQL extension — so Sherlock stores conversation embeddings and history in a single Oracle (PostgreSQL) instance. The same feature hardens SigNoz/OTEL configuration for both Sherlock and Cortex, and adds proper Docker health checks throughout.

**pgvector is not a new service.** It is a PostgreSQL extension installed into Oracle by switching the base image from `postgres:17-alpine` to `pgvector/pgvector:17-alpine`. The connection string, host, port, and credentials are unchanged.

## Motivation

| Problem | Impact |
|---------|--------|
| Dual-store complexity (Qdrant + PostgreSQL) | Two services to operate, two health checks, two failure modes |
| Qdrant adds ~400 MB to the `think` profile | Heavier dev startup with no benefit over pgvector for our scale |
| OTEL instrumentation is minimal in Sherlock and absent in Cortex | SigNoz shows no service data; distributed traces are incomplete |
| No Docker `healthcheck:` blocks on reasoner or persistence | Compose `depends_on` with no readiness signal is unreliable |

## Target Modules

| Service | Path | Impact |
|---------|------|--------|
| Persistence (Oracle) | `services/persistence/` | Image upgrade + init SQL |
| Reasoner (Sherlock) | `services/reasoner/` | pgvector migration + OTEL hardening |
| Cortex | `services/cortex/` | OTEL env vars only — no code changes |
| Platform profiles | `services/profiles.yaml` | Remove `vector-db` from `think` |

## Architecture

```mermaid
graph TB
    subgraph Before
        SH1[Sherlock] -->|vector search| QD[(Qdrant\narc-vector-db\n:6333)]
        SH1 -->|history| PG1[(PostgreSQL\narc-sql-db\n:5432)]
    end

    subgraph After
        SH2[Sherlock] -->|vector search\n+ history| PG2[(PostgreSQL + pgvector\narc-sql-db\n:5432)]
    end
```

### Connection Model

```
# Unchanged connection string
postgresql+asyncpg://arc:arc@arc-sql-db:5432/arc

# New column on sherlock.conversations
ALTER TABLE sherlock.conversations ADD COLUMN embedding vector(384);

# HNSW index for fast cosine search
CREATE INDEX ON sherlock.conversations USING hnsw (embedding vector_cosine_ops);
```

## Requirements

### R1 — pgvector Extension

- The Oracle (`arc-sql-db`) image MUST use `pgvector/pgvector:17-alpine` as base
- `CREATE EXTENSION IF NOT EXISTS vector;` MUST run on first boot via `initdb/`
- The `vector-db` service MUST be removed from the `think` profile

### R2 — Sherlock Memory Rewrite

- `SherlockMemory` MUST remove all Qdrant client code
- `SherlockMemory.save()` MUST write embedding + content to a single PostgreSQL row
- `SherlockMemory.search()` MUST query by cosine distance (`<=>` operator) with `user_id` filter
- The `sherlock.conversations` table MUST gain an `embedding vector(384)` column
- A HNSW index on the `embedding` column MUST be created on `init()`
- `SherlockMemory.health_check()` MUST return `{"postgres": bool}` (Qdrant key removed)

### R3 — Config Cleanup

- Settings `qdrant_host`, `qdrant_port`, `qdrant_collection` MUST be removed from `config.py`
- `qdrant-client>=1.9` MUST be removed from `pyproject.toml`
- `pgvector>=0.3.0` MUST be added to `pyproject.toml`
- All `SHERLOCK_QDRANT_*` env vars MUST be removed from `docker-compose.yml`

### R4 — Health Checks

**Docker `healthcheck:` blocks** (currently absent on both services):

| Service | Test command | Interval | Retries | Start period |
|---------|-------------|----------|---------|--------------|
| `arc-sherlock` | `wget -qO- http://localhost:8000/health` | 15s | 5 | 60s |
| `arc-sql-db` | `pg_isready -U arc` | 10s | 5 | 30s |

**API** — `/health/deep` response MUST no longer include `qdrant` key:
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

### R5 — SigNoz / OTEL Configuration

All standard OTEL env vars MUST be set in `docker-compose.yml` for Sherlock and Cortex so SigNoz auto-populates service metadata, environment, and namespace filters.

| Env Var | Value | Purpose |
|---------|-------|---------|
| `OTEL_SERVICE_NAME` | `arc-sherlock` / `arc-cortex` | Service identity in SigNoz |
| `OTEL_SERVICE_VERSION` | `0.1.0` | Version tag on spans |
| `OTEL_DEPLOYMENT_ENVIRONMENT` | `development` | SigNoz environment filter |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=arc-platform,...` | Namespace grouping |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://arc-friday-collector:4317` | Collector endpoint |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | Transport protocol |
| `OTEL_TRACES_SAMPLER` | `always_on` | 100% sampling in dev |
| `OTEL_PROPAGATORS` | `tracecontext,baggage` | W3C trace propagation |
| `OTEL_LOG_LEVEL` | `warn` | Suppress SDK noise |

For Cortex (Go): these env vars are consumed by the Go OTEL SDK directly — no code changes.
For Sherlock (Python): `OTEL_EXPORTER_OTLP_ENDPOINT` already mapped in `config.py`; remaining vars are standard and auto-consumed by the OTEL Python SDK.

### R6 — Tests

- All Qdrant mocks in `test_memory.py` MUST be replaced with SQLAlchemy async mocks
- `health_check()` tests MUST verify `{"postgres": bool}` shape (no `qdrant` key)
- Existing 40-test suite MUST remain green

### R7 — Contracts + Docs

- `contracts/openapi.yaml`: `/health/deep` response schema updated (remove `qdrant` property)
- `services/reasoner/service.yaml`: remove `vector-db` from `depends_on`, update description
- `services/reasoner/service.yaml`: add `healthcheck` block

## What Breaks — Full Inventory

| Location | Break | Fix |
|----------|-------|-----|
| `memory.py` | `qdrant_client` import | Remove — replace with pgvector |
| `memory.py` | `_init_qdrant()` | Remove — replaced by SQL DDL in `init()` |
| `memory.py` | `AsyncQdrantClient.search()` | Replace with SQL cosine distance query |
| `memory.py` | `AsyncQdrantClient.upsert()` | Replace with SQLAlchemy `session.add()` |
| `memory.py` | `health_check()` qdrant branch | Remove — single postgres check |
| `config.py` | `qdrant_host/port/collection` fields | Delete all three |
| `pyproject.toml` | `qdrant-client>=1.9` | Remove |
| `docker-compose.yml` | `SHERLOCK_QDRANT_HOST`, `SHERLOCK_QDRANT_PORT` | Remove |
| `main.py` | `"qdrant": dep_health.get("qdrant", False)` | Remove line |
| `main.py` | `DeepHealthResponse` components | Now only `postgres` + `nats` |
| `service.yaml` | `depends_on: vector-db` | Remove entry |
| `service.yaml` | description mentions Qdrant | Update text |
| `profiles.yaml` | `vector-db` in `think` | Remove entry |
| `test_memory.py` | All `AsyncQdrantClient` mocks | Replace with SQLAlchemy mocks |
| `contracts/openapi.yaml` | `qdrant` in health deep schema | Remove property |

## Out of Scope

- `services/vector/` — Cerebro/Qdrant service files remain untouched (other features may use it)
- Cortex source code — no Go changes needed (OTEL via env vars only)
- API v2 (`/v1/chat/completions`, streaming, history endpoints) — separate spec
