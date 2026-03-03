---
url: /arc-platform/specs-site/011-vector-setup/analysis-report.md
---
# Analysis Report: 011 pgvector Migration + Observability Hardening

**Date**: 2026-03-02
**Stage**: Pre-implementation
**Auditor**: Claude Code (read-only analysis)

***

## Coverage Matrix: Requirements → Plan → Tasks

| Req ID | Title | Plan Section | Task IDs | Status |
|--------|-------|--------------|----------|--------|
| R1 | pgvector Extension | Target Modules + Technical Context | TASK-010 | COVERED |
| R2 | Sherlock Memory Rewrite | Technical Context + Architecture | TASK-020 | COVERED |
| R3 | Config Cleanup | Target Modules | TASK-021 | COVERED |
| R4 | Health Checks | Risks & Mitigations | TASK-023, TASK-040, TASK-050 | COVERED |
| R5 | SigNoz/OTEL Configuration | Key Implementation Decisions | TASK-022, TASK-023 | COVERED |
| R6 | Tests | Project Structure | TASK-030 | COVERED |
| R7 | Contracts + Docs | Project Structure | TASK-031, TASK-050, TASK-900 | COVERED |

**Coverage Status**: All 7 requirements have corresponding tasks. No orphaned requirements.

***

## Gap Analysis

### 1. BLOCKER: Memory Protocol Pattern Not Explicitly Tested

**Location**: \[spec.md] R2, \[plan.md] "Memory Protocol (patterns.md §Repository)", \[tasks.md] TASK-001

**Issue**: TASK-001 defines `MemoryBackend` Protocol extraction, but:

* No explicit test is specified for the protocol itself
* TASK-030 (test\_memory.py rewrite) doesn't mention protocol compliance testing
* patterns.md §2 (Repository Pattern) states interfaces must be domain-specific — unclear if "memory backend interface" is explicit enough for type safety verification

**Risk**: Protocol extraction may not be validated, leaving future backends (Redis, Weaviate) without type safety guarantees.

**Recommendation**: Add acceptance criterion to TASK-030: "Protocol conformance verified via `mypy --strict` on `SherlockMemory` class — all methods match signature"

***

### 2. BLOCKER: asyncpg Vector Codec Event Hook — No Coverage in Dev Startup

**Location**: \[plan.md] "asyncpg + pgvector type registration" (lines 120–134)

**Issue**: The plan correctly identifies that `register_vector` must be called via a SQLAlchemy `connect` event. However:

* TASK-020 acceptance criteria state the hook must be "tested in test\_memory.py"
* But **no guidance on testing the event hook itself** — SQLAlchemy event registration is async/connection-scoped and notoriously hard to mock
* TASK-040 integration test doesn't explicitly verify the hook works end-to-end (e.g., actual vector round-trip)
* If the event hook fails silently, the UpsertTypeError only appears at runtime in `make dev`, not in `make reasoner-test`

**Recommendation**:

* TASK-020: Add acceptance criterion: "Integration test with real async engine + pgvector connection confirms vector codec loads (insert & retrieve vector column)"
* TASK-040: Add explicit vector round-trip test in end-to-end acceptance: "Search returns context with embedding distance ordering verified"

***

### 3. BLOCKER: OTEL Environment Variables — Conflicting Endpoint URLs

**Location**: \[plan.md] line 173, \[tasks.md] TASK-022 and TASK-023

**Issue**: Plan states:

* "Use `127.0.0.1:4317` for local binary runs (not `localhost` — IPv6 resolution issue on macOS with Docker Desktop)"
* "Docker Compose uses service DNS so `arc-friday-collector:4317` is correct inside containers"

But \[tasks.md] acceptance criteria for TASK-022 and TASK-023 do **not** specify which endpoint to use:

* Line 69 (TASK-022): "All 9 OTEL\_\* env vars present" — doesn't specify endpoint value
* Line 74 (TASK-023): Same — no guidance on endpoint choice for Sherlock's compose

**Risk**: Developers may hardcode `localhost:4317` in docker-compose.yml, breaking OTEL collection in containers; or use `127.0.0.1:4317` in compose, breaking local binary runs.

**Recommendation**: Update acceptance criteria:

* TASK-022: `OTEL_EXPORTER_OTLP_ENDPOINT` MUST be `http://arc-friday-collector:4317` (service DNS name, not localhost/127.0.0.1)
* TASK-023: Same as TASK-022
* Add comment in docker-compose.yml: `# Use service DNS name inside containers; for local binary runs, override with OTEL_EXPORTER_OTLP_ENDPOINT=127.0.0.1:4317`

***

### 4. WARNING: Missing Verify-No-Qdrant-Imports Task

**Location**: \[tasks.md] TASK-020 acceptance criteria

**Issue**: TASK-020 acceptance states "All `qdrant_client` imports removed" and `ruff check` + `mypy` pass. However:

* No explicit acceptance criterion for "grep/rg confirms zero `qdrant` mentions in source tree"
* TASK-999 (Reviewer) does mention "zero Qdrant imports in source" — but this should be verified during implementation, not just review

**Recommendation**: Add to TASK-020 acceptance: "Verify no stray `qdrant` imports: `rg 'qdrant' services/reasoner/src/ --type py` returns zero matches"

***

### 5. WARNING: Sentence-Transformer Model Download Not Addressed in Health Check

**Location**: \[plan.md] Risks § "Sentence-transformer model download on cold start" (L222)

**Issue**: Risk mitigation states "start\_period: 60s in healthcheck gives model time to load". However:

* \[spec.md] R4 specifies only `/health/deep` with no mention of retry logic or lazy initialization
* If model download takes >60s, healthcheck fails and `depends_on` sees failed status before LangGraph initializes
* No acceptance criterion in TASK-023 or TASK-040 validates model pre-loading or healthcheck behavior under slow network

**Recommendation**: Add to TASK-023 acceptance: "Healthcheck `start_period: 60s` confirmed; test with simulated slow model download shows service enters healthy state without timeout"

***

### 6. WARNING: HNSW Index Idempotency Not Explicitly Tested

**Location**: \[plan.md] Risks § "HNSW index creation fails on empty table" (L219)

**Issue**: Risk states "CREATE INDEX IF NOT EXISTS is idempotent; HNSW works on 0 rows". However:

* TASK-020 acceptance states "creates HNSW index" but doesn't specify idempotency testing
* TASK-030 (test\_memory.py) doesn't mention verifying `init()` can be called twice without error
* TASK-040 runs `make dev` once; no re-initialization test

**Recommendation**: Add to TASK-030 acceptance: "Test `SherlockMemory.init()` called twice on same schema — no `CREATE INDEX ... ALREADY EXISTS` error (idempotency verified)"

***

### 7. WARNING: Missing Cortex Service Verification in Integration Test

**Location**: \[tasks.md] TASK-040 acceptance criteria

**Issue**: Integration test verifies Sherlock (`curl localhost:8083/chat`) but does **not** verify Cortex health or OTEL visibility:

* No `curl localhost:CORTEX_PORT/health` check
* No verification that SigNoz UI shows Cortex service metadata
* TASK-999 (Reviewer) mentions "Cortex visible with service.namespace=arc-platform" — but this is a review checklist, not a dev acceptance criterion

**Recommendation**: Add to TASK-040 acceptance: "Cortex health endpoint returns 200 OK; SigNoz UI (if `reason` profile) shows Cortex with `service.namespace=arc-platform` tag"

***

### 8. INFO: Profiles.yaml Still References `vector-db`

**Location**: \[services/profiles.yaml] line 15, \[tasks.md] TASK-040

**Issue**: Current profiles.yaml shows `vector-db` in `think` profile (VERIFIED DURING AUDIT). TASK-040 acceptance correctly removes it, but:

* No task explicitly removes `vector-db` from the `reason` or `ultra-instinct` profiles (if present)
* \[plan.md] only mentions removal from `think`
* \[spec.md] R1 only states "removed from the `think` profile"

**Status**: Compliant with spec — removal from `think` is sufficient. Noted for completeness.

***

## Risks Assessment

| Risk ID | Risk | Severity | Mitigation | Status |
|---------|------|----------|-----------|--------|
| R1 | asyncpg vector codec not registered | HIGH | Event hook in `__init__` + integration test | MITIGATED (see Gap #2) |
| R2 | OTEL endpoint misconfigured in compose | HIGH | Clear endpoint value in acceptance criteria | MITIGATED (see Gap #3) |
| R3 | Qdrant imports not fully removed | MEDIUM | Grep verification in acceptance | MITIGATED (see Gap #4) |
| R4 | Model download exceeds healthcheck timeout | MEDIUM | `start_period: 60s` confirmed | MITIGATED (see Gap #5) |
| R5 | HNSW index creation not idempotent | LOW | `CREATE INDEX IF NOT EXISTS` + test twice | MITIGATED (see Gap #6) |
| R6 | Existing Qdrant data not migrated | LOW | Dev env only; fresh start acceptable | DOCUMENTED (plan.md L220) |
| R7 | pgvector image not in cache | MEDIUM | CI pre-pull; first run pulls from Docker Hub | DOCUMENTED (plan.md L221) |

***

## Parallel Execution Analysis

**Current Task DAG Review**:

Marked as `[P]` (parallel-safe):

* TASK-001 (MemoryBackend Protocol) — SAFE
* TASK-010 (Persistence image) — SAFE (no overlap with reasoner)
* TASK-022 (Cortex OTEL) — SAFE (isolated compose)
* TASK-023 (Sherlock OTEL + healthcheck) — **UNSAFE** — depends on TASK-001 not specified but required for proper memory protocol testing; recommend explicit dependency

Marked as dependent but could parallelize:

* TASK-020 (memory.py rewrite) depends on TASK-001 — CORRECT (Protocol must exist first)
* TASK-021 (Config cleanup) depends on TASK-001 — COULD BE PARALLEL to TASK-020 (independent cleanup); dependency is implicit but reasonable
* TASK-030 (test rewrite) depends on TASK-020 — CORRECT
* TASK-031 (health key cleanup) depends on TASK-020 — CORRECT

**Recommendation**: Verify that TASK-023 can truly start independently; if Docker healthcheck block needs to be aware of memory protocol, add explicit `TASK-001 → TASK-023` dependency.

***

## Constitution Compliance

| Principle | Applies | Status | Evidence |
|-----------|---------|--------|----------|
| I. Zero-Dependency CLI | N/A | N/A | No CLI changes |
| II. Platform-in-a-Box | REQUIRED | PASS | Single `docker compose up` still works; `think` profile simplified |
| III. Modular Services | REQUIRED | PASS | Each service (persistence, reasoner) self-contained; profiles.yaml updated cleanly |
| IV. Two-Brain Separation | REQUIRED | PASS | All changes Python (intelligence) + SQL (infra); no Go logic in Python code |
| V. Polyglot Standards | REQUIRED | PASS | Python: ruff + mypy enforced; 12-Factor config; async/await patterns correct; OTEL env vars standard |
| VI. Local-First | N/A | N/A | No CLI changes |
| VII. Observability by Default | REQUIRED | PASS | Full OTEL instrumentation wired for Sherlock + Cortex; SigNoz pre-configured; health checks added |
| VIII. Security by Default | REQUIRED | PASS | Non-root containers unchanged; no secrets in config; pgvector adds no new attack surface |
| IX. Declarative Reconciliation | N/A | N/A | No CLI changes |
| X. Stateful Operations | N/A | N/A | No CLI changes |
| XI. Resilience Testing | REQUIRED | PASS | Single-store eliminates dual-write failure mode; health checks added; HNSW index resilient to empty table |
| XII. Interactive Experience | N/A | N/A | No CLI changes |

**Overall Constitution Status**: 6 PASS, 6 N/A. No violations detected.

***

## Patterns.md Compliance

| Pattern | Applies | Status | Evidence |
|---------|---------|--------|----------|
| Factory/DI | REQUIRED (Python) | PASS | `SherlockMemory` accepts engine + logger via **init**; no globals |
| Repository | REQUIRED (Python) | PASS | `MemoryBackend` Protocol defined; `SherlockMemory` implements domain-specific methods (search, save, health\_check) |
| Config Precedence | REQUIRED (Python) | PASS | Config cleanup removes hard-coded qdrant\_\* settings; OTEL via 12-Factor env vars |
| Error Handling | REQUIRED | PASS | Async errors from pgvector wrapped; no silent failures |
| Testing Standards | REQUIRED | PASS | pytest async tests; mocks at SQLAlchemy boundary only; coverage targets 75% critical |
| XDG Base Directory | N/A | N/A | Applies to CLI only |
| Observability Pattern (Go) | N/A | N/A | No Go service logic changes |

**Overall Patterns Status**: 5 PASS, 2 N/A. No violations.

***

## Summary

**Blockers**: 3 (memory protocol testing, OTEL endpoint clarity, asyncpg codec coverage)
**Warnings**: 5 (no-qdrant-imports verification, model download health check, HNSW idempotency, Cortex verification, parallel safety of TASK-023)
**Observations**: 1 (vector-db removal already compliant with spec intent)

### Recommendation

**PAUSE TO FIX BLOCKERS**

The spec and plan are well-structured, but three critical issues must be resolved before implementation begins:

1. **Clarify TASK-020 acceptance** to explicitly verify asyncpg vector codec works end-to-end (not just code presence)
2. **Specify exact OTEL endpoint values** in TASK-022 and TASK-023 acceptance criteria (`arc-friday-collector:4317` inside compose; document override for local binary)
3. **Add integration test to TASK-040** verifying actual vector round-trip through pgvector (save + search + verify ordering by distance)

Once these are addressed, all 7 requirements map cleanly to 12 tasks with safe parallelism. No constitution violations detected. Ready for implementation after blockers resolved.

***

**Audit Complete**: 2026-03-02 16:00 UTC
