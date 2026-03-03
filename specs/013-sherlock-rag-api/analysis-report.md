# Analysis Report: 013-Sherlock-RAG-API

**Date:** 2026-03-03  
**Stage:** Pre-implementation  
**Spec Status:** Approved  
**Auditor:** Claude Code (read-only analysis)

---

## Executive Summary

013 is a well-scoped, architecturally sound feature extending Sherlock (012) into a Universal RAG engine. All user scenarios, functional requirements, and success criteria are clearly defined with proper edge case coverage. The tasks are properly parallelized (19 of 30 can run concurrently), dependencies form a valid DAG, and constitution/pattern compliance is strong.

**Verdict:** READY FOR IMPLEMENTATION (with minor clarifications noted below)

---

## 1. Coverage Matrix

### Functional Requirements (FR-1 to FR-15)

| FR | User Story(ies) | Plan Section | Task(s) | Status |
|----|-----------------|--------------|---------|--------|
| FR-1 | US-1 | Files API | TASK-050 | ✓ |
| FR-2 | US-1, US-6 | Files CRUD | TASK-050 | ✓ |
| FR-3 | US-14 | File download | TASK-050 | ✓ |
| FR-4 | US-2, US-15 | Vector Store CRUD | TASK-051 | ✓ |
| FR-5 | US-3, US-9 | Async/Sync ingest | TASK-051 | ✓ |
| FR-6 | US-3 | File-within-store CRUD | TASK-051 | ✓ |
| FR-7 | US-8, US-11 | Hybrid search | TASK-051 | ✓ |
| FR-8 | US-5 | Embeddings API | TASK-052 | ✓ |
| FR-9 | US-4, US-11, US-13 | RAG chat with tools | TASK-053, TASK-054 | ✓ |
| FR-10 | US-3 | IngestPipeline | TASK-030, TASK-031, TASK-040 | ✓ |
| FR-11 | US-8 | HybridRetriever | TASK-021, TASK-041 | ✓ |
| FR-12 | US-12 | NATS handlers | TASK-055 | ✓ |
| FR-13 | US-7 | RAG disabled → 503 | TASK-050, TASK-051, TASK-052, TASK-053 | ✓ |
| FR-14 | US-13 | Token counting | TASK-054 | ✓ |
| FR-15 | — | DB schema init | TASK-002, TASK-021 | ✓ |

**Result:** 15/15 FRs mapped to tasks. ✓ COMPLETE

### Non-Functional Requirements (NFR-1 to NFR-9)

| NFR | Description | Plan Coverage | Task(s) | Status |
|-----|-------------|----------------|---------|--------|
| NFR-1 | Content tracing gate | Config → TASK-001 | TASK-001 | ✓ |
| NFR-2 | Ingest failure handling | Application layer | TASK-040 | ✓ |
| NFR-3 | Think profile byte-identical with RAG disabled | Config gate | TASK-001, TASK-060 | ✓ |
| NFR-4 | Ruff + mypy strict | Quality standards | TASK-001 through TASK-071 | ✓ |
| NFR-5 | ≥75% coverage on rag/, routers | Test tasks | TASK-070, TASK-071 | ✓ |
| NFR-6 | Hybrid search latency ≤100ms | SQL optimized | TASK-021 | ✓ |
| NFR-7 | Reranker latency ≤20ms | CrossEncoder | TASK-023 | ✓ |
| NFR-8 | OTEL counter/timer/error pattern | All routers | TASK-050 through TASK-055 | ✓ |
| NFR-9 | All 012 tests pass unchanged | Integration | TASK-071 | ✓ |

**Result:** 9/9 NFRs covered. ✓ COMPLETE

### Success Criteria (SC-1 to SC-12)

| SC | Requirement | Task Coverage | Status |
|----|-------------|----------------|--------|
| SC-1 | `GET /v1/files` returns 200 | TASK-050, TASK-071 | ✓ |
| SC-2 | Full ingest cycle end-to-end | TASK-040, TASK-051, TASK-071 | ✓ |
| SC-3 | RAG chat grounded (not hallucinated) | TASK-053, TASK-054, TASK-071 | ✓ |
| SC-4 | Embeddings returns 384-element vector | TASK-052, TASK-071 | ✓ |
| SC-5 | RAG disabled → 503, 012 unaffected | TASK-001, TASK-050-052, TASK-071 | ✓ |
| SC-6 | Lint zero errors | TASK-001 through TASK-071 | ✓ |
| SC-7 | ≥75% coverage; 012 tests pass | TASK-070, TASK-071 | ✓ |
| SC-8 | `usage.prompt_tokens` non-zero | TASK-054, TASK-071 | ✓ |
| SC-9 | NATS ingest request→result | TASK-055, TASK-071 | ✓ |
| SC-10 | Hybrid search alpha blending | TASK-021, TASK-041, TASK-071 | ✓ |
| SC-11 | SigNoz metrics populated | TASK-050-052, TASK-055 | ✓ |
| SC-12 | service.yaml bumped v0.3.0; storage added | TASK-062 | ✓ |

**Result:** 12/12 SCs covered. ✓ COMPLETE

### User Stories (US-1 to US-15)

All 15 user stories are covered by one or more tasks. US-14 and US-15 (P3 — nice to have) are included in FR-3 and FR-4 respectively.

**Result:** 15/15 USs covered. ✓ COMPLETE

---

## 2. Edge Cases Audit

The spec defines 11 edge cases (lines 283-300). Verification:

| Edge Case | Scenario | Acceptance Criterion | Task(s) | Status |
|-----------|----------|----------------------|---------|--------|
| EC-1 | Unsupported extension | 400 error | TASK-050 (files_router) | ✓ |
| EC-2 | File exceeds max size (50 MB) | 400 error | TASK-050 (files_router) | ✓ |
| EC-3 | Ingest fails (corrupt PDF, parser exception) | `status=failed`, error_message in DB | TASK-040 (IngestPipeline exception handling) | ✓ |
| EC-4 | MinIO unreachable during upload | 503 not 500 | TASK-020 (MinIO adapter error handling) | ✓ |
| EC-5 | pgvector unavailable during search | Graceful degradation (empty context) | TASK-021 (pgvector adapter) + TASK-053 (graph node) | ✓ |
| EC-6 | Non-existent vector_store_id | Empty results, rest still searched | TASK-041 (HybridRetriever) | ✓ |
| EC-7 | Same file added to VS twice | Idempotent (returns existing row) | TASK-051 (vector_stores_router) | ✓ |
| EC-8 | `hybrid_alpha=0.0` (pure keyword) | FTS-only scoring | TASK-021 (SQL weighted scoring) | ✓ |
| EC-9 | `hybrid_alpha=1.0` (pure dense) | Dense cosine only | TASK-021 (SQL weighted scoring) | ✓ |
| EC-10 | `?sync=true` on file >30s | Timeout → fallback to 202 | TASK-051 (asyncio.wait_for with timeout) | ✓ |
| EC-11 | Delete file during ingest in-progress | `status=failed` in DB | TASK-040 (exception handling) | ✓ |

**Result:** 11/11 edge cases covered. ✓ COMPLETE

---

## 3. CI Build Success Criteria (BC-1 to BC-5)

From spec.md lines 331–461, the CI investigation requires these criteria:

| Criterion | Description | Plan Coverage | Task(s) | Status |
|-----------|-------------|----------------|---------|--------|
| BC-1 | Cold build ≤5 minutes | M-1 (CPU-only torch) + M-3 (uv) | TASK-004 | ✓ |
| BC-2 | Warm build (cache hit) ≤90s | M-1 + M-3 | TASK-004 | ✓ |
| BC-3 | typecheck/test jobs ≤3 min each | M-2 (pip cache) | TASK-005 | ✓ |
| BC-4 | torch CPU-only (`torch.version.cuda` = None) | M-1 | TASK-004 | ✓ |
| BC-5 | No regression on existing tests | All tasks | TASK-071 | ✓ |

**Result:** All 5 BC criteria mapped to tasks. ✓ COMPLETE

---

## 4. Task Dependency Analysis

### DAG Validation

Analyzed tasks.md dependency graph (lines 23–110). **Result: Valid DAG, no cycles.** ✓

Key dependency chains verified:
- **T001 (config)** → T002 (DB) → T010 (models) → T011 (ports) → T020–T031 (adapters/parsers)
- **T040 (ingest)** ← T020, T021, T022, T030, T031
- **T041 (retriever)** ← T021, T022, T023
- **T050–T055 (routers)** ← T042 (RAGInfra)
- **T060 (main.py wire)** ← T050–T055
- **T070–T071 (tests)** ← T060
- **T999 (reviewer)** ← ALL

All dependencies are **acyclic and properly ordered.**

### Parallelization Analysis

Tasks marked `[P]` in tasks.md: **19 out of 30 tasks can run in parallel.**

**Verified parallel-safe groups:**

1. **Setup Phase (2 tasks, 2 parallel):**
   - TASK-004 (Dockerfile)
   - TASK-005 (CI workflow)

2. **Parallel Batch A — Adapters (4 tasks, 4 parallel after TASK-011):**
   - TASK-020 (MinIO)
   - TASK-021 (pgvector)
   - TASK-022 (embedder)
   - TASK-023 (reranker)

3. **Parallel Batch B — Parsers + Chunker (2 tasks, 2 parallel after TASK-010):**
   - TASK-030 (parsers)
   - TASK-031 (chunker)

4. **Parallel Batch C — HTTP Routers (6 tasks, 6 parallel after TASK-042):**
   - TASK-050 (files_router)
   - TASK-051 (vector_stores_router)
   - TASK-052 (embeddings_router)
   - TASK-053 (graph.py RAG node)
   - TASK-054 (openai_router tiktoken)
   - TASK-055 (NATS RAG handler)

5. **Parallel Batch D — Config + Wiring (3 tasks, 2 parallel after setup):**
   - TASK-061 (docker-compose.yml) [P]
   - TASK-062 (service.yaml bump) [P]

6. **Parallel Batch E — Tests (2 tasks, 2 parallel after TASK-060):**
   - TASK-070 (unit tests) [P]
   - TASK-071 (integration tests) [P]

7. **Parallel Batch F — Docs (1 task, 1 parallel after TASK-060):**
   - TASK-900 (OpenAPI/AsyncAPI) [P]

**All parallel tasks verified to have non-overlapping module paths.** ✓

---

## 5. Mandatory Tasks Audit

| Task | Purpose | Status |
|------|---------|--------|
| TASK-900 | Docs/links (OpenAPI, AsyncAPI) | ✓ Present |
| TASK-999 | Reviewer verification | ✓ Present |

**Result:** Both mandatory tasks present with clear acceptance criteria. ✓ COMPLETE

---

## 6. Constitution Compliance (v2.2.0)

Reviewed against `.specify/memory/constitution.md`. Plan.md already includes a constitution table (lines 155–171). Cross-check:

| Principle | Applies | Plan Status | Compliant | Evidence |
|-----------|---------|------------|-----------|----------|
| I. Zero-Dependency CLI | [ ] | N/A | — | No CLI changes |
| II. Platform-in-a-Box | [x] | PASS | [x] | RAG disabled by default; think profile unchanged; MinIO in reason profile only |
| III. Modular Services | [x] | PASS | [x] | All changes in `services/reasoner/`; no new service directory |
| IV. Two-Brain | [x] | PASS | [x] | Python only (parsing, chunking, embedding, reranking) |
| V. Polyglot Standards | [x] | PASS | [x] | FastAPI + Pydantic v2 + ruff + mypy strict + pytest; no AI attribution per CLAUDE.md |
| VI. Local-First | [ ] | N/A | — | No CLI component |
| VII. Observability | [x] | PASS | [x] | 6 new OTEL metrics; every route follows counter/timer/error pattern; tasks include `event_type` logging |
| VIII. Security | [x] | PASS | [x] | MinIO creds via `SecretStr`; file content never in logs/spans (gated by `SHERLOCK_CONTENT_TRACING=false`) |
| IX. Declarative | [ ] | N/A | — | No CLI component |
| X. Stateful Ops | [ ] | N/A | — | No CLI component |
| XI. Resilience | [x] | PASS | [x] | Ingest failure → DB status=failed (API unaffected); pgvector down → empty ctx (chat continues) |
| XII. Interactive | [ ] | N/A | — | No CLI component |

**Result:** 7/7 applicable principles compliant. ✓ READY

---

## 7. Patterns Compliance (v1.0.0)

Reviewed against `.specify/memory/patterns.md`. Task design aligns with required patterns:

| Pattern | Applies | Design | Status |
|---------|---------|--------|--------|
| Factory/DI | [x] | `RAGInfra` dataclass holds all ports; factory function in TASK-042 | ✓ |
| Repository | [x] | Port-based architecture (FileStore, VectorStore, Embedder, Reranker protocols) | ✓ |
| Config Precedence | [x] | Env → Pydantic Settings with defaults (TASK-001) | ✓ |
| Error Handling | [x] | Custom exceptions, structured error responses, non-500 on expected failures (e.g., 503 MinIO) | ✓ |
| Testing Standards | [x] | pytest fixtures, table-driven, ≥75% coverage requirement (TASK-070, TASK-071) | ✓ |
| XDG Base Directory | [ ] | N/A (Python service, not CLI) | — |
| OTEL Observability (Go) | N/A | — | — |
| UI Service (Go) | N/A | — | — |

**Result:** 5/5 applicable patterns covered. ✓ READY

---

## 8. Gaps Found

### Blockers (must fix before implementation)

None identified. All major gaps are pre-integration clarifications, not implementation blockers.

---

### Warnings (should address)

**Warning-1: Service.yaml version and docker-compose.yml coordination**
- **File:** `services/reasoner/service.yaml` and `docker-compose.yml`
- **Issue:** Plan.md (line 23) says docker-compose.yml changes are needed, but TASK-061 says `arc-storage` container is "added to compose (or referenced)." This is ambiguous.
- **Recommendation:** Clarify in TASK-061 acceptance criteria whether:
  - Arc-storage is added as a new service in the `reason` profile, OR
  - It's referenced via existing `compose.override.yml` or merged profile config
  - Current `docker-compose.yml` (line 30) shows no explicit `depends_on` — how is service startup ordering enforced?
  - Look at how other services (arc-sql-db, arc-messaging) are composed

**Warning-2: `/health/deep` MinIO component missing**
- **File:** `main.py` lifespan (TASK-060)
- **Issue:** Plan.md says "/health/deep includes `minio: bool` component when `rag_enabled`" but existing health_deep() (main.py:283) only checks postgres + nats.
- **Recommendation:** TASK-060 acceptance must explicitly add MinIO health check to `/health/deep` endpoint:
  ```python
  if state.rag:
      components["minio"] = state.rag.file_store.is_healthy()
  ```

**Warning-3: Reranker lazy init may exceed timeout on first request**
- **File:** TASK-023 (reranker_router)
- **Issue:** TASK-023 says "lazy CrossEncoder init on first call (model name from settings)" but spec.md (H-5) notes the model is ~200 MB. First chat request with RAG could timeout if reranker download takes >30s sync timeout.
- **Recommendation:** Document in TASK-023 acceptance criteria:
  - Model is cached after first download (subsequent calls use cached version)
  - Consider pre-downloading model at image build (mitigation H-5 — currently not required by spec)

**Warning-4: TASK-061 docker-compose changes undefined**
- **File:** `docker-compose.yml` modification in TASK-061
- **Issue:** Plan.md (line 23) says "arc-storage container added to compose (or referenced) in reason profile configuration" but doesn't specify whether docker-compose.yml is the right place or if a separate override should be used.
- **Recommendation:** TASK-061 acceptance criteria should clarify:
  - Is docker-compose.yml modified directly?
  - Or does `reason` profile use a separate `compose.reason.yml` overlay?
  - How are `SHERLOCK_RAG_*` env vars scoped to `reason` profile only?

---

### Observations (nice to know, not blockers)

**Observation-1: Tiktoken token counting in FR-14 fixes 012 gap**
- Current config.py and openai_router already import tiktoken, but 012 returns `(0, 0, 0)`. TASK-054 must wire this.
- Recommendation: Verify existing tiktoken import is correct and accessible.

**Observation-2: Duplicate embedding models**
- `sentence-transformers/all-MiniLM-L6-v2` is used by both SherlockMemory (embeddings for conv history) and RAGInfra (knowledge chunks).
- This is by design (plan.md line 239) — "EmbedderAdapter accepts encoder instance, main.py passes memory._encoder".
- Recommendation: Confirm in TASK-042 that `RAGInfra.embedder` receives `memory._encoder` instance (not a new load).

**Observation-3: Qdrant mentioned in plan.md but removed from spec**
- Plan.md (line 99) references "qdrant" in the RAG package diagram, but no Qdrant integration is in the spec.
- The diagram shows pgvector adapters only. This is correct (pgvector is the chosen backend).
- Recommendation: Verify diagram in plan.md line 99 doesn't confuse pgvector (Postgres extension) with Qdrant (separate vector DB).

**Observation-4: OTEL metrics namespace**
- Spec.md SC-11 expects `sherlock.rag.uploads.total`, `sherlock.rag.ingest.latency`, etc.
- Confirm metric names exactly match in all router implementations (TASK-050–TASK-055).

**Observation-5: No explicit cancellation token for async tasks**
- TASK-051 specifies `?sync=true` with `asyncio.wait_for(timeout)` fallback to 202.
- If timeout occurs, the background task continues but is not tracked after client disconnects.
- Consider: What happens if the same file is re-added before the first ingest completes?
  - Plan.md EC-7 (line 293) says "idempotent — returns existing row" but doesn't specify if re-add during in-flight ingest is atomic.
  - Recommendation: TASK-051 should clarify: insert vector_store_files with unique constraint (vs_id, file_id) to prevent duplicates.

---

## 9. Missing or Unclear Acceptance Criteria

### Minor Clarity Issues (all resolvable in implementation)

1. **TASK-002 (DB schema)**: Plan.md line 393 shows `fts_vector GENERATED ALWAYS` but doesn't specify PostgreSQL version requirement. Acceptance criteria should add: "Postgres 12+ required (GENERATED ALWAYS supported)." Oracle runs PG 17 ✓, but document it.

2. **TASK-021 (hybrid search SQL)**: Plan.md describes the algorithm but acceptance criteria should explicitly test both `alpha=0.0` and `alpha=1.0` edge cases with fixed test data.

3. **TASK-040 (IngestPipeline)**: Specify timeout for large file parsing (> 30s). Currently doc says "configurable timeout; if exceeded → returns 202" but no default. Recommendation: add `ingest_timeout_s` setting or use `sync_timeout_s`.

4. **TASK-060 (main.py wiring)**: Document when RAGInfra is None (rag_enabled=false) — all routers must return 503 immediately. Confirm check happens before any logic in routers.

5. **TASK-071 (integration tests)**: Spec requires ≥75% coverage on `rag/`, `files_router.py`, `vector_stores_router.py`, `embeddings_router.py`. Acceptance should specify command: `pytest tests/ --cov=sherlock.rag,sherlock.files_router,sherlock.vector_stores_router,sherlock.embeddings_router --cov-fail-under=75`.

---

## 10. Cross-Module Dependency Risks

### Potential Issues (all mitigated in plan)

| Risk | Severity | Mitigation | Task |
|------|----------|-----------|------|
| MinIO unreachable at startup | M | Error logged, service starts degraded, routers return 503 | TASK-020, TASK-060 |
| pgvector unavailable at startup | M | DB schema init best-effort (logs warning), app continues; search returns empty | TASK-021, TASK-060 |
| File deletion during in-flight ingest | M | FK cascade deletes chunks; `vector_store_files` status=failed with error_message | TASK-040, TASK-051 |
| Reranker model download blocks HTTP request | M | Lazy init; download happens on first chat request only; subsequent cached | TASK-023 |
| CrossEncoder model not in cache | L | Lazy download, user sees first request latency spike (~5s); mitigated by H-5 (image pre-download, optional) | TASK-023 |

**Result:** All risks identified and mitigated. ✓ MANAGED

---

## 11. Spec-to-Plan-to-Tasks Traceability

Sampling verification (10 user stories):

| US | Spec Section | Plan Evidence | Task Chain | Mapped |
|----|--------------|----------------|-----------|--------|
| US-1 (upload) | L136–140 | "Files API" line 12, 183 | TASK-050 | ✓ |
| US-3 (add to VS) | L148–152 | "Ingestion Flow" line 90 | TASK-051, TASK-040 | ✓ |
| US-4 (RAG chat) | L154–158 | "RAG Chat Flow" line 117 | TASK-053, TASK-054 | ✓ |
| US-5 (embeddings) | L160–164 | "Embeddings API" line 183 | TASK-052 | ✓ |
| US-7 (disabled error) | L172–176 | "RAGInfra factory check" line 236 | TASK-050–052 | ✓ |
| US-8 (search) | L180–184 | "Hybrid Search SQL" line 139 | TASK-051, TASK-041 | ✓ |
| US-9 (sync ingest) | L186–190 | "Sync timeout" line 262 | TASK-051 | ✓ |
| US-12 (NATS) | L204–208 | "NATS handlers" line 78 | TASK-055 | ✓ |
| US-13 (token count) | L210–214 | "Tiktoken wiring" line 270 | TASK-054 | ✓ |
| US-14 (download) | L218–222 | "File download" line 183 | TASK-050 | ✓ |

**Result:** All sampled stories correctly mapped. ✓ COMPLETE

---

## 12. Summary Verdict

### Completion Status

- **Coverage:** 15 FR + 9 NFR + 12 SC + 15 US + 11 EC + 5 BC = **67/67 requirements covered** ✓
- **Tasks:** 30 total, 19 parallelizable, all depend on 2 setup tasks ✓
- **Mandatory tasks:** TASK-900 (docs), TASK-999 (reviewer) present ✓
- **Constitution:** 7/7 applicable principles compliant ✓
- **Patterns:** 5/5 applicable patterns implemented ✓
- **Edge cases:** 11/11 covered with explicit acceptance criteria ✓
- **DAG validation:** No cycles, proper dependency ordering ✓

### Known Limitations (not blockers)

1. **Docker-compose profile wiring** — TASK-061 needs clarification on whether to modify docker-compose.yml directly or use compose overlays
2. **MinIO health check** — TASK-060 must add MinIO to `/health/deep` when `rag_enabled=true`
3. **Reranker lazy init timeout** — Document expected latency spike on first request

### Recommendation

**READY FOR IMPLEMENTATION** — All critical pieces are in place. Team can begin parallel execution immediately:

**Start immediately (no dependencies):**
- Group A: TASK-004, TASK-005 (CI build fixes)
- TASK-001, TASK-002, TASK-003 (config/schema setup)

**After setup (Day 1–2):**
- Group B: TASK-010, TASK-011 (domain models/ports)
- Parallel: TASK-020–023 (adapters), TASK-030–031 (parsers), plus existing TASK-001–003

**Mid-week (Phase 3–4):**
- Group C: TASK-040–042 (application layer)
- Parallel: TASK-050–055 (routers) + TASK-061–062 (config/service.yaml)

**End of week (Phase 5–6):**
- TASK-060 (main.py wire) — blocks TASK-070/071
- TASK-070–071 (tests)
- TASK-900 (docs)
- TASK-999 (reviewer)

**Estimated duration:** 1–2 weeks with 4–6 parallel agents across 3 phases.

---

## Appendix: File Paths Referenced

- `/services/reasoner/src/sherlock/config.py` — Settings additions
- `/services/reasoner/src/sherlock/main.py` — AppState, lifespan, router wiring
- `/services/reasoner/src/sherlock/rag/` — New package (domain, adapters, application, parsers)
- `/services/reasoner/src/sherlock/files_router.py` — New file
- `/services/reasoner/src/sherlock/vector_stores_router.py` — New file
- `/services/reasoner/src/sherlock/embeddings_router.py` — New file
- `/services/reasoner/pyproject.toml` — Dependency additions
- `/services/reasoner/service.yaml` — Version bump to 0.3.0
- `/services/reasoner/docker-compose.yml` — Env var additions
- `/services/reasoner/Dockerfile` — CPU-torch + uv optimization
- `/services/persistence/initdb/004_sherlock_rag_schema.sql` — New SQL init
- `/.github/workflows/reasoner-images.yml` — pip cache addition
- `/specs/013-sherlock-rag-api/contracts/openapi.yaml` — 13 new paths
- `/specs/013-sherlock-rag-api/contracts/asyncapi.yaml` — 4 new channel pairs

---

**End of Analysis Report**
