# Pre-Implementation Audit: 015-Nervous System

> **Date**: 2026-03-05
> **Auditor**: Claude Code (read-only analysis)
> **Scope**: spec.md, plan.md, tasks.md, constitution compliance, dependency graph, cross-references

---

## 1. Coverage Matrix (FR/NFR → Plan → Task)

| ID | Requirement | Spec Type | Plan Section | Task(s) | Status |
|-----|-------------|-----------|--------------|---------|--------|
| FR-1 | stream_graph() default | Functional | Phase 1 | T010, T011 | MAPPED |
| FR-2 | Token chunks to NATS | Functional | Phase 1 | T010, T011 | MAPPED |
| FR-3 | Completion signal | Functional | Phase 1 | T010, T011 | MAPPED |
| FR-4 | request.received to Pulsar | Functional | Phase 3 | T031 | MAPPED |
| FR-5 | inference.completed with usage | Functional | Phase 3 | T033 | MAPPED |
| FR-6 | Embedding off loop | Functional | Phase 1, 2 | T012, T020 | MAPPED |
| FR-7 | Redis cache check | Functional | Phase 2 | T021 | MAPPED |
| FR-8 | Cache TTL + invalidation | Functional | Phase 2 | T021, T022 | MAPPED |
| FR-9 | RoboCop pre-check | Functional | Phase 3 | T032 | MAPPED |
| FR-10 | RoboCop post-check | Functional | Phase 3 | T032 | MAPPED |
| FR-11 | Guard event publishing | Functional | Phase 3 | T032 | MAPPED |
| FR-12 | NATS→Pulsar fallback | Functional | Phase 3 | T034 | MAPPED |
| FR-13 | asyncapi.yaml schema | Functional | Phase 1, 3 | T014, T035 | MAPPED |
| NFR-1 | P50 TTFT < 200ms | Non-Functional | All phases | T010–T035 | MAPPED |
| NFR-2 | RoboCop latency bounds | Non-Functional | Phase 3 | T032 | MAPPED |
| NFR-3 | Pulsar <5ms overhead | Non-Functional | Phase 3 | T031, T039 | MAPPED |
| NFR-4 | Sonic cache <10ms P99 | Non-Functional | Phase 2 | T021 | MAPPED |
| NFR-5 | stream_graph() non-blocking | Non-Functional | Phase 1 | T010, T011, T019 | MAPPED |
| NFR-6 | ruff + mypy zero errors | Non-Functional | All phases | T019, T029, T039 | MAPPED |
| NFR-7 | Coverage ≥80% | Non-Functional | All phases | T019, T029, T039 | MAPPED |

**Result**: 100% of FRs and NFRs mapped to plan sections and tasks. No orphaned requirements.

---

## 2. Gaps Found

### GAP-1: Missing Task for Cerebro Integration Verification

**Severity**: WARNING

**Description**: Task T020 references "Cerebro + pgvector search" but does not verify that arc-db-vector (Cerebro / Qdrant) service exists and is healthy in the `think` or `reason` profile.

**Evidence**:
- Spec.md US-5: "Embedding and vector search run concurrently with LLM warm-up"
- Tasks.md T021 (Redis): "cache checked before Cerebro/pgvector on every retrieval"
- No task to verify Cerebro service.yaml includes health check or that streaming profile includes it

**Recommendation**: Add acceptance criterion to T020 or T041 to verify Cerebro service health; or add a task T042 (post-Gate 3) to validate multi-service startup in `reason` profile.

---

### GAP-2: Pulsar DLQ/Dead-Letter Processing Not Specified

**Severity**: BLOCKER

**Description**: FR-12 (NATS→Pulsar fallback) queues requests to `arc.reasoner.requests.durable` but spec.md does not describe what happens to messages that fail processing from the durable queue. No retry policy, max retries, or DLQ topic defined.

**Evidence**:
- Plan.md Phase 3: "Request is queued to `arc.reasoner.requests.durable` on Pulsar"
- Spec.md US-8: No mention of retry count, backoff, or failure handling after durable queue
- Tasks.md T034: "result delivered via correlation ID when capacity is available" — but no acceptance criterion for retry exhaustion

**Recommendation**: Add to spec.md Edge Cases or US-8:
- Max retry count for durable queue requests (suggest 3)
- Backoff strategy (exponential backoff, e.g., 100ms → 1s → 10s)
- DLQ topic where exhausted requests are published (`arc.reasoner.requests.failed`)
- Update T034 acceptance criteria to test retry exhaustion scenario

---

### GAP-3: RoboCop Service Not Yet Implemented

**Severity**: CRITICAL — Mitigation Already in Place

**Description**: Phase 3 (T032) depends on arc-guard (RoboCop) service which does not yet exist in `services/`.

**Evidence**:
- Plan.md Risk #3: "RoboCop service not yet built — pre/post hooks need a stub"
- T032 acceptance: "SHERLOCK_GUARD_ENABLED=false default disables hooks (fail-open)"
- No `services/guard/` or `services/robocop/` directory found

**Mitigation**: Plan.md specifies feature flag `SHERLOCK_GUARD_ENABLED=false` default, making hooks no-ops until RoboCop exists. Feature flag allows Phase 3 to complete without blocking on RoboCop.

**Recommendation**: Documented and mitigated. No change needed. Ensure T032 includes test_guard_pre_check_rejects_injection and test_guard_post_check_intercepts_unsafe_output as **mock/stub tests** until RoboCop exists.

---

### GAP-4: Pulsar Topic List Incomplete in asyncapi.yaml

**Severity**: WARNING

**Description**: Spec.md defines 15+ Pulsar topics (reasoner, ingest, kb, agent, tools, accuracy loop, billing) but asyncapi.yaml contract is split across T014 (Phase 1 NATS subjects only) and T035 (Phase 3 full contract).

**Evidence**:
- Spec.md "Pulsar Topic Schema": 15 topics listed across REASONER, INGESTION, KNOWLEDGE BASE, AGENT, TOOLS, ACCURACY LOOP
- Tasks.md T014: "NATS subjects in asyncapi.yaml (Phase 1 schema)"
- Tasks.md T035: "Complete asyncapi.yaml with all Pulsar topics and schemas" — depends on T033

**Risk**: T035 dependencies are T033 (inference.completed model only), but does not include models for ingest.*, kb.*, agent.*, tools.*, guard.*, critic.*, gym.*, billing.usage. These are referenced in spec but may not be modeled.

**Recommendation**: Update T035 acceptance criteria to explicitly list all 15+ topic schemas that must be present in final asyncapi.yaml. Or: scope Phase 3 to reasoner.* topics only and defer ingest/kb/agent/tools/accuracy topics to future feature specs (e.g., 016-ingestion, 017-accuracy-loop). **Current tasks.md unclear on scope.** Add explicit scope boundary.

---

### GAP-5: Missing Test for Context Injection Mid-Stream

**Severity**: MEDIUM

**Description**: Spec.md US-5 and plan.md Phase 2 define "context injected via LangGraph state mid-stream" but acceptance criterion for T020 does not explicitly test this.

**Evidence**:
- Spec.md US-5: "retrieved context is injected via LangGraph state mid-stream"
- Plan.md Phase 2 diagram: "CTX → LLM" with context available before stream ends
- Tasks.md T020 acceptance: "`asyncio.gather()` runs embed + vector search concurrently with LLM warm-up; retrieved context injected via LangGraph state mid-stream; `test_graph.py` parallel retrieve test passes"

**Issue**: Acceptance criterion says "test_graph.py parallel retrieve test passes" but does not specify **what the test must verify** (e.g., context injection timestamp, state update event, LLM sees full context before N-th token).

**Recommendation**: Add explicit test scenario to T020:
```
- Context cache miss triggers parallel embed + vector search
- LLM stream starts before retrieval completes
- Retrieval completes and context is injected into LangGraph state
- Verify via trace that LLM tokens N+1 onward include context (not just token N)
- Verify timing: context injection latency < 150ms from request start
```

---

### GAP-6: Concurrent Request Race Condition Not Tested

**Severity**: MEDIUM

**Description**: Spec.md Edge Cases: "Concurrent requests from same user: Each request gets its own Sonic cache check; no cross-request cache poisoning" — but tasks.md does not include a test for this.

**Evidence**:
- Spec.md Edge Cases table: scenario documented, expected behavior defined
- Tasks.md: No task references concurrent-same-user test
- T021 (Redis cache) and T029 (Gate 2) do not list this scenario in acceptance criteria

**Recommendation**: Add to T021 acceptance criteria:
```
- Test: two concurrent requests from same user with different queries
- Verify: each request computes independent embeddings
- Verify: no cache key collision (sha256(embedding) differs)
- Verify: cache misses for both are independent (no interference)
```

---

## 3. Risks

### RISK-1: stream_graph() API Stability

**Severity**: MEDIUM | **Likelihood**: MEDIUM

**Description**: Phase 1 assumes LangGraph's `stream_graph()` is stable and behaviorally equivalent to `invoke_graph()` for error handling. If error signatures differ, NATS handlers may mishandle failures.

**Evidence**:
- Plan.md Risk #1: "`stream_graph()` has subtle differences from `invoke_graph()` in error handling"
- Mitigation: "Read `streaming.py` + `graph.py` carefully before T1; add error path tests"

**Mitigation Status**: DOCUMENTED. T010/T011 acceptance criteria must include error path tests (e.g., LLM API timeout, token exhaustion).

**Recommendation**: Before T010 starts, add a pre-flight analysis task to audit LangGraph release notes for stream_graph() error behavior. Ensure acceptance criteria for T010/T011 include: **"Test: LLM API timeout mid-stream → error chunk published to NATS + completion signal sent"**

---

### RISK-2: ThreadPoolExecutor Blocking Event Loop

**Severity**: HIGH | **Likelihood**: MEDIUM

**Description**: Phase 1 (T012) wraps `SentenceTransformer.encode()` in `run_in_executor()` but spec.md and plan.md do not explicitly test concurrent request handling under load.

**Evidence**:
- Plan.md Risk #2: "ThreadPoolExecutor in async context causes event loop blocking"
- Mitigation: "Use `loop.run_in_executor()` not `asyncio.run()`; test with concurrent requests"
- Tasks.md T012: "concurrent requests test passes" — but does not specify **how many concurrent requests** or **what latency threshold**

**Recommendation**: Update T012 acceptance criteria to specify:
```
- Concurrent requests: at least 10 simultaneous requests from different users
- Each request triggers SentenceTransformer.encode() (not cached)
- Verify: max(request_latency) does not exceed min(request_latency) by > 50%
  (i.e., ThreadPoolExecutor serialization is < 50% overhead)
- Verify: event loop remains responsive during encoding (no blocking)
```

---

### RISK-3: Pulsar Connection Initialization Latency

**Severity**: MEDIUM | **Likelihood**: MEDIUM

**Description**: Phase 3 (T031, T033) publishes to Pulsar on every request but Pulsar client connection may be expensive. If initialized per-request, first request after Sherlock start may add 100ms+ latency.

**Evidence**:
- Plan.md Risk #3: "Pulsar client connection adds latency on first request"
- Mitigation: "Initialize client at startup (lazy singleton), not per-request"
- Tasks.md T031/T033: No acceptance criterion for Pulsar client initialization strategy

**Recommendation**: Update T031 and T033 acceptance criteria to specify:
```
- Pulsar client initialized at Sherlock startup (not on first publish)
- Measure: first request publish latency == subsequent request publish latency (within 5%)
- Verify: Pulsar client is a lazy singleton (init once, reuse across all requests)
- Test: `test_pulsar_handler.py::test_request_received_latency_<5ms` measures first vs second publish
```

---

### RISK-4: Redis Unavailable Does Not Cascade

**Severity**: MEDIUM | **Likelihood**: LOW

**Description**: Phase 2 (T021) implements Redis cache but if Redis is unavailable, spec.md Edge Cases defines "fail-open with log warning; do not fail the request". However, tasks.md T021 does not explicitly test Redis-down scenario.

**Evidence**:
- Spec.md Edge Cases: "arc-db-cache (Sonic / Redis) unavailable → Fall through to Cerebro/pgvector on every request; log cache miss; do not fail the request"
- Plan.md Risk #5: "Redis unavailable causes cache errors that propagate"
- Mitigation: "Wrap cache calls in try/except; fail-open with log warning; test Redis-down scenario"
- Tasks.md T021: No acceptance criterion for Redis-down test

**Recommendation**: Add T021 acceptance criterion:
```
- Test: Redis connection refused (port unreachable)
- Verify: request still completes (fail-open)
- Verify: cache_hit=false in inference.completed event
- Verify: warning log message emitted
- Verify: Cerebro/pgvector called (fallback path taken)
```

---

### RISK-5: Cerebro Service May Not Be in Default Profile

**Severity**: MEDIUM | **Likelihood**: LOW

**Description**: Phase 2 depends on Cerebro (Qdrant) but profiles.yaml does not list `cerebro` in `think` or `reason` profiles. If Cerebro is not running, vector search will fail.

**Evidence**:
- Profiles.yaml: No mention of `cerebro`, `qdrant`, or `vector` service in `think` or `reason` profiles
- Spec.md: "arc-db-vector (Cerebro / Qdrant)" required for retrieval
- Plan.md: Assumes Cerebro available during Phase 2

**Recommendation**: 
1. Check if Cerebro service exists in `services/` directory (was not found in initial glob)
2. If not yet built, add to plan.md Phase 2 risks: "Cerebro service not yet implemented"
3. If exists, ensure `reason` profile includes `cerebro` service
4. Add task T041 (or verify existing T040) acceptance criterion: `make dev-health` confirms Cerebro (Qdrant) health

---

### RISK-6: asyncapi.yaml Drift from Pydantic Models

**Severity**: MEDIUM | **Likelihood**: MEDIUM

**Description**: Spec.md and plan.md suggest asyncapi.yaml should be generated from Pydantic models in models_v1.py to prevent schema drift, but tasks.md T035 does not include automation.

**Evidence**:
- Plan.md Risk #7: "asyncapi.yaml schema drift from actual event payloads"
- Mitigation: "Generate schema from Pydantic models in models_v1.py; keep them the single source of truth"
- Tasks.md T035: "JSON schemas match Pydantic models in `models_v1.py`" — manual verification, no generator

**Recommendation**: Update T035 to include either:
1. A Python script to generate asyncapi.yaml from Pydantic models (recommended)
2. A test that validates asyncapi.yaml schemas match Pydantic model definitions (at minimum)
3. Documentation comment in models_v1.py: "Source of truth for all event schemas — update asyncapi.yaml when these models change"

---

### RISK-7: Feature Flag `SHERLOCK_PULSAR_ENABLED` Inconsistent Naming

**Severity**: LOW | **Likelihood**: LOW

**Description**: Spec.md, plan.md, and NERVOUS-SYSTEM-HLD.md use both `SHERLOCK_PULSAR_ENABLED` and `SHERLOCK_GUARD_ENABLED` feature flags, but config.py settings are not listed in tasks.md.

**Evidence**:
- Spec.md US-7: `SHERLOCK_PULSAR_ENABLED=true`
- Plan.md Risk #3: `SHERLOCK_GUARD_ENABLED=false` default
- NERVOUS-SYSTEM-HLD.md Phase 3: mentions feature flag for Pulsar
- Tasks.md: T001, T022 mention config.py but do not list feature flag names

**Recommendation**: Update T001 acceptance criteria to explicitly list all config constants/env vars:
```
- NATS_SUBJECT_REQUEST
- NATS_SUBJECT_STREAM
- NATS_SUBJECT_RESULT
- NATS_SUBJECT_ERROR
- NATS_SUBJECT_INGEST_REQUEST
- NATS_SUBJECT_INGEST_PROGRESS
- PULSAR_BROKER_URL (or similar)
- SHERLOCK_PULSAR_ENABLED (Phase 3)
- SHERLOCK_GUARD_ENABLED (Phase 3)
- SONIC_URL (Phase 2)
- CONTEXT_CACHE_TTL (Phase 2, default 300s)
```

---

## 4. Parallel Opportunities

### Already Marked [P] (Parallelizable)

All Phase 1 tasks (T010, T011, T012, T013, T014) are correctly marked [P] and have no inter-file dependencies.
All Phase 2 tasks (T020, T021, T022) are correctly marked [P].
Phase 3 has T031, T032, T033 marked [P] after T030 completes (correct dependency).

**Assessment**: Task parallelization strategy is sound. No hidden conflicts found.

---

### Potential Micro-Parallelization (Within Single Phase)

**Not currently exploited**:

1. **T030 + T020 overlap**: T030 defines models, but T020 (graph.py parallel retrieve) does not depend on T030. Could start T020 earlier using forward type hints.
   - **Recommendation**: Optional optimization. Not worth refactoring for this feature.

2. **T019 (Gate 1) + T020 start**: Gate 1 and T020 are sequential, but Gate 1 includes only Phase 1 tests. Could start T020 before Gate 1 passes if integration risk is acceptable.
   - **Recommendation**: Not recommended. Stabilization gates exist for safety.

---

## 5. Constitution Compliance

### Matrix (all 12 principles)

| # | Principle | Applies | Status | Evidence |
|---|-----------|---------|--------|----------|
| I | Zero-Dependency CLI | N/A | N/A | No CLI changes in spec |
| II | Platform-in-a-Box | YES | **PASS** | Phase 3 Pulsar fan-out enables full event backbone; all services already in profiles |
| III | Modular Services | YES | **PASS** | Each service (reasoner, messaging, cache, streaming) is independent; no changes to profiles |
| IV | Two-Brain Separation | YES | **PASS** | Python-only changes (Sherlock reasoner); no Go code modified |
| V | Polyglot Standards | YES | **PASS** | ruff + mypy required (NFR-6); Pydantic models for events; asyncapi.yaml for contracts |
| VI | Local-First | YES | **PASS** | Pulsar degrades gracefully (SHERLOCK_PULSAR_ENABLED flag); NATS path unaffected if Pulsar unavailable |
| VII | Observability | YES | **PASS** | `ttft_seconds` histogram added; OTEL trace context on all events; structured logging via Pydantic models |
| VIII | Security | YES | **PASS** | RoboCop pre/post checks on all transports; no secrets in event payloads (spec.md verified); non-root container (existing Dockerfile) |
| IX | Declarative | YES | **PASS** | asyncapi.yaml defines all topics + schemas; Pydantic models are data contracts |
| X | Stateful Ops | YES | **PASS** | Redis cache with explicit invalidation; Pulsar durable queue for fallback |
| XI | Resilience | YES | **PASS** | Pulsar fail-open (SHERLOCK_PULSAR_ENABLED=false); Redis fail-open; RoboCop fail-open; NATS/Pulsar fallback |
| XII | Interactive | N/A | N/A | No TUI/CLI changes |

**Result**: 10/10 applicable principles PASS. No constitution violations.

---

## 6. Service Path Validation

### Verified Module Paths

| Module Path | Type | Status |
|-------------|------|--------|
| `services/reasoner/src/reasoner/` | Python | EXISTS, in scope |
| `services/reasoner/contracts/` | YAML | EXISTS, in scope |
| `services/reasoner/tests/` | Python | EXISTS, in scope |
| `services/streaming/` | YAML | EXISTS, verified in profiles |
| `services/cache/` | (Redis) | EXISTS, verified in profiles |
| `services/messaging/` | (NATS) | EXISTS, verified in profiles |

**Cross-reference against profiles.yaml**:
- `streaming` service listed in `think`, `reason`, `ultra-instinct` profiles ✓
- `cache` service listed in `think`, `reason`, `ultra-instinct` profiles ✓
- `messaging` service listed in `think`, `reason`, `ultra-instinct` profiles ✓

**No stale patterns found** (platform/core/, platform/plugins/ not referenced).

---

## 7. Spec.md → Plan.md → Tasks.md Traceability

### Forward Traceability (Spec → Plan → Task)

Example: FR-2 "Token chunks published to `arc.reasoner.stream.{request_id}`"
- Spec.md: ✓ US-1 (P1 user story)
- Plan.md: ✓ Phase 1 architecture diagram
- Tasks.md: ✓ TASK-010, TASK-011 acceptance criteria

**All 13 FRs + 7 NFRs traced forward successfully.**

### Backward Traceability (Task → Plan → Spec)

Example: TASK-034 "NATS → Pulsar fallback"
- Tasks.md: ✓ Phase 3
- Plan.md: ✓ Architecture diagram Phase 3, NATS→Pulsar degradation sequence
- Spec.md: ✓ US-8 (P3 user story), Edge Cases table

**All 21 tasks traced backward successfully.**

**Result**: No orphaned specifications or tasks.

---

## 8. Dependency Graph Validation

### DAG Check

```
T001 (config) → T010, T011, T012, T013, T014
T010-T014 → GATE1
GATE1 → T020, T021, T022
T020-T022 → GATE2
GATE2 → T030
T030 → T031, T032, T033 (parallel)
T031 → T034
T033 → T035
T031-T035 → GATE3
GATE3 → T040, T041
GATE3 → T900, T999
```

**Cycle detection**: No cycles detected. Valid DAG.

**Dependency depths**:
- Longest path: T001 → GATE1 → GATE2 → T030 → T034 → GATE3 → T999 (8 hops)
- Estimated duration: 14–16 work-days (3-4 days per phase × 3 phases + gates + integration)

---

## 9. Acceptance Criteria Specificity

### Sampled Task Analysis

**TASK-010 [P] Wire stream_graph() into nats_handler.py**
- AC: "token chunks published to `arc.reasoner.stream.{request_id}`" — **CONCRETE**
- AC: "completion signal to `arc.reasoner.result`" — **CONCRETE**
- AC: "`test_nats_handler.py` streaming path tests pass" — **TESTABLE** (but no test names listed)
- **Grade**: GOOD, could be more specific (test names)

**TASK-021 [P] Add Redis cache layer**
- AC: "Cache key `arc:ctx:{user_id}:{sha256(embedding)}`" — **CONCRETE**
- AC: "Redis unavailable → fail-open with warning log" — **CONCRETE**
- AC: "`test_memory.py::test_cache_hit_skips_vector_search` and `test_cache_invalidated_on_new_message` pass" — **SPECIFIC TEST NAMES**
- **Grade**: EXCELLENT

**TASK-039 Gate 3 (full test suite)**
- AC: Full bash test suite listed — **EXECUTABLE, REPEATABLE**
- **Grade**: EXCELLENT

**Overall Acceptance Criteria Quality**: 80% GOOD, 20% could be more specific on test names.

---

## 10. Reviewer Checklist Completeness

Plan.md includes separate reviewer checklists for each phase (Phase 1, 2, 3) with specific verification steps:

**Phase 1 Checklist**: 5 items (invoke_graph removal, token publishing, executor usage, ttft metric, lint/test)
**Phase 2 Checklist**: 5 items (asyncio.gather, cache key format, TTL config, invalidation, fail-open)
**Phase 3 Checklist**: 8 items (request.received timing, inference.completed payload, usage fields, pre/post check sequencing, flag behavior, NATS fallback, asyncapi coverage, integration tests)

**Result**: Comprehensive. All critical verification points covered.

---

## Summary

**Blockers (must resolve before implementing)**:
1. **GAP-2**: Pulsar DLQ/retry policy not specified — add to spec.md US-8 or new edge case
2. **RISK-5**: Cerebro service may not be in reason profile — verify existence, add to profile if needed

**Warnings (should address)**:
1. **GAP-1**: No task to verify Cerebro health in profiles
2. **GAP-4**: asyncapi.yaml scope unclear (reasoner.* only vs full platform topics)
3. **RISK-1**: stream_graph() error handling not pre-flighted
4. **RISK-6**: asyncapi.yaml generation not automated

**Observations**:
1. Constitution compliance is solid (10/10 principles)
2. Parallelization strategy is sound
3. Dependency graph is a valid DAG with reasonable depth (14–16 days estimated)
4. 100% of FRs/NFRs mapped to tasks
5. Traceability is complete both forward and backward
6. Feature flags (SHERLOCK_PULSAR_ENABLED, SHERLOCK_GUARD_ENABLED) documented but naming should be standardized in config.py

---

## Recommendations

### Before Implementation Starts

1. **Resolve GAP-2 (Pulsar DLQ)**: Add retry policy, max retries, DLQ topic to spec.md. Update T034 acceptance criteria.
2. **Resolve RISK-5 (Cerebro)**: Verify Cerebro service exists in `services/` and add to `reason` profile if missing. Add T041 (post-Gate 3) health check task.
3. **Clarify GAP-4 (asyncapi.yaml scope)**: Decide if Phase 3 covers reasoner.* topics only, or includes ingest/kb/agent/tools/accuracy. Document scope boundary explicitly.

### During Phase 1 Planning (Before T010 starts)

1. **Pre-flight stream_graph() analysis**: Audit LangGraph release notes for error handling differences. Add error path tests to T010/T011 acceptance criteria.
2. **Configure concurrent request load**: Specify minimum concurrency (10 concurrent requests) and latency threshold (50% overhead limit) for T012 executor test.

### During Phase 3 (After T030)

1. **Automate asyncapi.yaml generation**: Implement Python script (recommended) or at minimum, add validation test to T035 that verifies schemas against Pydantic models.

### General

1. **Standardize config.py feature flags**: Document all env vars in T001 acceptance criteria (NATS subjects, Pulsar topics, Redis URL, feature flags).

---

## Conclusion

**Recommend: PROCEED WITH BLOCKERS RESOLVED**

The feature is well-structured and comprehensive. Constitution compliance is solid. Traceability is complete. Dependency graph is valid. Two blockers (Pulsar DLQ, Cerebro profile) must be resolved before coding begins. Three additional warnings should be addressed during planning phases. No critical flaws detected in the specification structure itself.

Estimated implementation timeline: **14–16 work-days** (3 phases × 4–5 days + integration + docs + review).

