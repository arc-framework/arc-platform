# Analysis Report: 004-dev-setup
**Date:** 2026-02-28  
**Stage:** Pre-implementation

---

## Executive Summary

The 004-dev-setup specification is **READY FOR IMPLEMENTATION** with minor clarifications needed. The spec is comprehensive, well-structured, and the plan includes a solid architecture. However, there are several gaps in acceptance criteria, task ordering, and service metadata that should be resolved before development begins.

**Status**: 2 BLOCKERS, 4 WARNINGS, 5 OBSERVATIONS

---

## Blockers (Must Resolve)

### BLOCKER-1: Incomplete OTEL Service Metadata
**Location**: spec.md FR-6, plan.md, tasks.md TASK-013  
**Issue**: The spec requires creating `services/otel/service.yaml` for the full OTEL stack, but currently only `services/otel/observability/service.yaml` and `services/otel/telemetry/service.yaml` exist.

- spec.md FR-6 says: "Create `services/otel/service.yaml` — full OTEL stack metadata: `codename: otel`, `health: http://localhost:3301/api/v1/health`, `depends_on: []`"
- Current structure has `observability/service.yaml` (codename: `friday`) and `telemetry/service.yaml` (codename: `friday-collector`)
- The `observability/service.yaml` has `depends_on: [telemetry]`, creating a cross-directory dependency

**Clarification Needed**:
- Should `services/otel/service.yaml` be a new top-level service metadata file that references both sub-services?
- Or should the spec instead reference the existing `services/otel/observability/service.yaml` which already has `codename: friday`?
- The `ultra-instinct` profile lists `otel` as a service, but the registry parser will see `friday`, `friday-collector`, and potentially `otel` — which is correct?

**Impact**: Tasks T013, T040 (Makefile) depend on clarity here.

---

### BLOCKER-2: `profiles.yaml` Incomplete for `think` Profile
**Location**: spec.md, tasks.md TASK-010, plan.md line 249  
**Issue**: TASK-010 requires adding `friday-collector` to the `think` profile, but the spec's sequence diagram shows all 5 services starting (flash, sonic, strange, friday-collector, cortex).

Current `services/profiles.yaml`:
```yaml
think:
  services:
    - cortex
    - flash
    - strange
    - sonic
```

Does NOT include `friday-collector`.

- spec.md section "Startup Sequence (think profile)" (line 72-110) explicitly shows `friday-collector` in Layer 0
- spec.md FR-9 states: "add `friday-collector` to the `think` profile service list"
- TASK-010 acceptance criteria state this must happen

**Impact**: US-1 acceptance criteria require 5 services. Without this change, smoke test will fail.

**Action**: Confirm TASK-010 must be completed before TASK-040 (Makefile).

---

## Warnings (Should Address)

### WARNING-1: Task Ordering Dependency Error
**Location**: tasks.md dependency graph, lines 28-44  
**Issue**: TASK-040 (Makefile) lists 12 prerequisites (T001, T010-T014, T020-T024, T030-T031) but has no sequential ordering constraint.

According to plan.md (line 264):
> "### Phase 2 — Makefile (after Phase 1 complete)"

The Makefile phase depends on **all** Phase 1 items. However:
- The dependency graph shows all prerequisites, but doesn't indicate the critical path
- Phase 1 includes both foundational YAML patches AND script implementations
- The mermaid graph makes this clear, but the task list doesn't mark TASK-040 with explicit "Phase 3: Implementation" labeling

**Clarification**: In `tasks.md`, explicitly mark each task with its **Phase** number. Current format `[TASK-NNN] [P]` should expand to `[TASK-NNN] [P] [PHASE-N]`:
- Example: `[TASK-001] [P] [PHASE-1]` (Setup)
- Example: `[TASK-040] [SEQUENTIAL] [PHASE-3]` (Makefile — after all PHASE-1/2 complete)

**Impact**: Implementers may attempt TASK-040 before upstream scripts are ready, causing circular dependency failures.

---

### WARNING-2: Missing Timeout Specifications in service.yaml
**Location**: plan.md line 131, spec.md FR-7  
**Issue**: `services/otel/telemetry/service.yaml` currently lacks a `timeout` field.

Current file (5 lines):
```yaml
codename: friday-collector
tech: arc-friday-collector
upstream: signoz/signoz-otel-collector
ports:
  - 4317   # OTLP gRPC
  - 4318   # OTLP HTTP
health: http://localhost:13133/
```

Missing:
- `timeout: 60` (or appropriate value)
- `depends_on: []` (explicit empty list for clarity)

TASK-014 acceptance criteria state:
> "File has `codename: friday-collector`, `health: http://localhost:13133/`, `timeout: 60`"

**Action**: TASK-014 acceptance criteria must include adding `timeout` and `depends_on` fields if missing.

---

### WARNING-3: `parse-registry.sh` Scope Ambiguity
**Location**: plan.md line 57, spec.md FR-2  
**Issue**: The spec states `parse-registry.sh` scans `services/*/service.yaml` AND `services/*/*/service.yaml` (nested).

Current actual structure has 6 service.yaml files across 2 levels:
- Level 1: `services/cache/`, `services/cortex/`, `services/messaging/`, `services/streaming/`
- Level 2: `services/otel/observability/`, `services/otel/telemetry/`

The awk-based parser must handle both levels. However:
- `parse-registry.sh` acceptance criteria (TASK-021, line 107) state: "output contains ... for all `service.yaml` files found under `services/`"
- This is correct but doesn't explicitly mention how nested directories are discovered

**Action**: FR-2 should clarify:
> "Recursively scan `services/` directory for all `service.yaml` files at any depth; emit registry variables for each"

---

### WARNING-4: Existing `cortex/service.yaml` Differs from Spec
**Location**: spec.md FR-12, tasks.md TASK-011  
**Issue**: Spec says to "remove `oracle` from `depends_on`", but `cortex/service.yaml` **already lists** `oracle`:

```yaml
depends_on:
  - flash    # arc-messaging (NATS)
  - strange  # arc-streaming (Pulsar)
  - oracle   # arc-sql-db (Postgres)       ← MUST REMOVE
  - sonic    # arc-cache (Redis)
  - friday-collector    # arc-friday-collector (OTEL)
```

This is CORRECT per spec, but the comment suggests it's a **known broken state**:
> "# TODO: re-add oracle when persistence service lands" (spec.md line 199)

**Action**: Good. This is already flagged in TASK-011. No change needed; just confirming the spec aligns with reality.

---

## Observations (Nice to Know)

### OBS-1: Missing Makefile Target for `dev-regen`
**Location**: plan.md line 324, spec.md not explicitly mentioned  
**Issue**: plan.md references a `dev-regen` target:
```makefile
dev-regen:    # force-rebuild .make/ files
```

But spec.md does not list this as a requirement (no FR-16 or similar).

**Recommendation**: Either add `dev-regen` to spec.md's FR list (after FR-15) or remove from Makefile target list. Currently it's only documented in plan.md.

---

### OBS-2: Docker Network Names Not in Service YAML
**Location**: spec.md line 91, plan.md line 148  
**Issue**: The spec states that `make dev` creates `arc_platform_net` and `arc_otel_net` Docker networks idempotently.

However:
- These network names are hardcoded in the Makefile target
- Individual `service.yaml` files do NOT declare which network they join
- This couples network management to the root Makefile rather than per-service configuration

**Recommendation**: Document this as a known limitation in the spec's "Edge Cases" section. Consider future enhancement to allow per-service network assignment via `service.yaml`.

---

### OBS-3: Health Check Timeout Edge Case
**Location**: spec.md "Edge Cases" (line 232)  
**Issue**: The edge case section covers timeout well:
```
| Service health check times out | `wait-for-health.sh` exits 1: `✗ flash did not become healthy after 60s` |
```

But NFR-3 states:
```
`make dev` for the `think` profile must complete in under 3 minutes on a warm Docker cache
(Pulsar cold-start ~90s is the expected bottleneck)
```

The sequence diagram shows:
- `strange` (Pulsar) timeout: 120s (line 101)

**Calculation**:
- flash health wait: 60s
- sonic health wait: 30s
- strange health wait: 120s
- friday-collector health wait: 30s
- (serial, gated by layer)
- cortex health wait: 60s

Total: 60 + 30 + 120 + 30 + 60 = **300 seconds = 5 minutes**

This exceeds the 3-minute target in NFR-3.

**Recommendation**: Clarify in NFR-3 whether the 3-minute target includes Docker pull time for cold-start (first run), or only assumes warm cache. Current wording is ambiguous. If cold-start Pulsar can take 90s, and we wait 120s for health, plus 150s for other services, we're at ~5 minutes minimum.

---

### OBS-4: Polyglot Standards Gap — Comments in Shell Scripts
**Location**: constitution.md Principle V, plan.md line 182  
**Issue**: Constitution v2.2.0 adds rules for comments:
```
- Comment the *why*, never the *what* — code should be self-explanatory
- Only comment non-obvious intent, algorithmic trade-offs, or external constraints
```

The spec's acceptance criteria for shell scripts (TASK-020 through TASK-024) do NOT mention comment style or docstring conventions.

**Recommendation**: Add acceptance criteria for all 5 shell scripts:
- "All functions have docstrings describing purpose and usage"
- "Comments explain non-obvious logic (e.g., why DFS topological sort vs. Kahn's algorithm explanation in resolve-deps.sh)"

---

### OBS-5: FR-16 Phantom Requirement
**Location**: plan.md line 131 mentions "FR-16 (new)" but spec.md does NOT define FR-16
**Issue**: plan.md line 249 states:
```
- FR-16 (new): `services/cache/service.yaml` — update health endpoint
```

But spec.md's functional requirements list ends at FR-15. This requirement was **added during planning** but not formally added to the spec.

**Recommendation**: Either:
1. Add FR-16 to spec.md's functional requirements section, OR
2. Remove from plan.md and fold the `services/cache/service.yaml` update into TASK-012

Clarify in spec: Is changing sonic's health from `redis-cli ping` to `docker exec arc-cache redis-cli ping` required for this feature?

---

## Coverage Matrix

| Requirement | Plan Section | Task IDs | Status |
|-------------|--------------|----------|--------|
| FR-1 (parse-profiles.sh) | Parallel Batch B | T020 | MAPPED |
| FR-2 (parse-registry.sh) | Parallel Batch B | T021 | MAPPED |
| FR-3 (resolve-deps.sh) | Parallel Batch C | T022 | MAPPED |
| FR-4 (wait-for-health.sh) | Parallel Batch C | T023 | MAPPED |
| FR-5 (check-dev-prereqs.sh) | Parallel Batch C | T024 | MAPPED |
| FR-6 (otel/service.yaml) | Parallel Batch A | T013 | **BLOCKER** — Metadata unclear |
| FR-7 (otel/telemetry/service.yaml) | Parallel Batch A | T014 | **WARNING** — Missing timeout |
| FR-8 (Makefile update) | Phase 3 | T040 | MAPPED (blocked on Phase 1/2) |
| FR-9 (profiles.yaml patch) | Parallel Batch A | T010 | **BLOCKER** — Not yet applied |
| FR-10 (otel.mk aliases) | Parallel Batch D | T030 | MAPPED |
| FR-11 (cortex.mk aliases) | Parallel Batch D | T031 | MAPPED |
| FR-12 (cortex/service.yaml patch) | Parallel Batch A | T011 | MAPPED (already correct state) |
| FR-13 (.gitignore patch) | Parallel Batch A | T001 | MAPPED |
| FR-14 (Docker networks) | Phase 3 | T040 | MAPPED (sub-requirement of T040) |
| FR-15 (Shell script conventions) | Phase 1 | T020-T024 | MAPPED |
| (NFR) No new tool deps | Implicit | All | PASS (only awk, curl, docker) |
| (NFR) Auto-regeneration | Phase 3 | T040 | MAPPED |
| (NFR) 3-minute startup | Implicit | T040 | **OBS** — May exceed target |
| (NFR) Script conventions | Phase 1 | T020-T024 | MAPPED |
| (NFR) Backward compat | Phase 3 | T040 | MAPPED |

---

## Gaps Found

| Gap | Severity | Location | Recommendation |
|-----|----------|----------|-----------------|
| GAP-1 | BLOCKER | TASK-010 not yet applied to profiles.yaml | Apply `friday-collector` to `think` profile before implementation |
| GAP-2 | BLOCKER | otel/service.yaml metadata undefined | Clarify whether FR-6 creates new file or references existing `observability/service.yaml` with codename `friday` |
| GAP-3 | WARNING | TASK-014 missing timeout field acceptance criteria | Add `timeout: 60` and `depends_on: []` to acceptance criteria |
| GAP-4 | WARNING | Phase labeling missing from task list | Mark each task with explicit `[PHASE-N]` for clarity |
| GAP-5 | OBSERVATION | dev-regen target not in spec | Add to FR list or remove from plan.md |
| GAP-6 | OBSERVATION | FR-16 phantom requirement | Formalize sonic health endpoint change as FR-16 or fold into T012 |
| GAP-7 | OBSERVATION | Shell script comment standards not in acceptance criteria | Add docstring + comment style requirements to TASK-020 through TASK-024 |
| GAP-8 | OBSERVATION | Startup time target may be unachievable | Clarify whether 3-minute NFR-3 target includes cold-start or only warm cache |

---

## Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| RISK-1 | TASK-010 not applied before TASK-040 | HIGH | Code breaks smoke test; `make dev` starts only 4 services instead of 5 | **HIGH** | Make TASK-010 a hard blocker for TASK-040 in dependency graph |
| RISK-2 | awk parser fails on edge-case YAML formatting | MEDIUM | Scripts silently emit empty registry, `make dev` fails with cryptic message | **MEDIUM** | Validate all 6 existing `service.yaml` files match expected format; document YAML schema |
| RISK-3 | `parse-registry.sh` misses nested `service.yaml` files | HIGH | Nested services (otel/observability, otel/telemetry) not registered; `make dev` skips them | **MEDIUM** | Ensure `find` recursively scans all directories; test with `-maxdepth -1` (unlimited) |
| RISK-4 | Docker network creation fails in shared environments | MEDIUM | Multiple developers on same machine create port conflicts | **LOW** | `docker network create` is idempotent; add comment in Makefile explaining this |
| RISK-5 | Circular dependency in otel services | MEDIUM | observability depends_on telemetry; if ever reversed, cycle detection must catch it | **LOW** | resolve-deps.sh implements Kahn's algorithm; cycle detection is built-in |
| RISK-6 | Startup timeout exceeds 3-minute NFR-3 target | MEDIUM | Slow machines or Docker daemon lag cause timeouts; developers blame the feature | **MEDIUM** | Document environment requirements; add `TIMEOUT_OVERRIDE` mechanism for CI/slow systems |

---

## Parallel Execution Opportunities

Current task structure already has excellent parallelization:
- **Phase 1** (SETUP): 1 task (T001) — independent
- **Phase 2** (FOUNDATIONAL): 10 tasks in 4 batches — all parallelizable
  - Batch A (YAML): 6 tasks (T010-T014, T001) — **FULLY PARALLEL**
  - Batch B (Parse scripts): 2 tasks (T020-T021) — **FULLY PARALLEL**
  - Batch C (Orchestration): 3 tasks (T022-T024) — **FULLY PARALLEL**
  - Batch D (.mk aliases): 2 tasks (T030-T031) — **FULLY PARALLEL**
- **Phase 3** (INTEGRATION): 1 task (T040) — **SEQUENTIAL** (blocks on all Phase 1/2)
- **Phase 4** (POLISH): 2 tasks (T900, T999) — **SEQUENTIAL** (after T040+T050)

**No improvement opportunities identified.** Current parallelization is optimal. ✓

---

## Constitution Compliance

| Principle | Applies | Status | Evidence |
|-----------|---------|--------|----------|
| I. Zero-Dependency CLI | **NO** | n/a | Feature is Makefile + shell only; no CLI changes |
| II. Platform-in-a-Box | **YES** | **PASS** | `make dev` = single command starts full `think` profile automatically; complies with "docker-compose up" or equivalent requirement |
| III. Modular Services | **YES** | **PASS** | Framework reads per-service `service.yaml`; new service = new directory + yaml + mk + Dockerfile; no central wiring required |
| IV. Two-Brain Separation | **NO** | n/a | Shell scripting only; no Go/Python introduced |
| V. Polyglot Standards | **YES** | **PARTIAL** | Scripts use `common.sh` helpers (✓), follow color/symbol conventions (✓), BUT acceptance criteria lack comment/docstring standards (⚠) |
| VI. Local-First | **NO** | n/a | CLI-only principle |
| VII. Observability | **YES** | **PASS** | `friday-collector` added to `think` profile by default; ensures OTEL traces/metrics collection on every dev startup |
| VIII. Security | **YES** | **PASS** | No secrets in scripts or generated files (✓); port pre-checks prevent unintended exposure (✓); containers already run non-root (existing config) |
| IX. Declarative Reconciliation | **YES** | **PASS** | `profiles.yaml` + `service.yaml` = declarative source of truth; Make reconciles via generated files (✓); no imperative state drift |
| X. Stateful Operations | **NO** | n/a | CLI-only principle |
| XI. Resilience | **YES** | **PASS** | Health-check gating between dependency layers (✓); fail-fast on unregistered or circular deps (✓); `wait-for-health.sh` implements retry logic |
| XII. Interactive Experience | **NO** | n/a | CLI-only principle |

**Overall Constitution Status**: ✓ **COMPLIANT** (7 applies, 7 pass; 5 n/a)

---

## Recommendations

### MUST FIX (Before Implementation)

1. **Resolve BLOCKER-1**: Clarify OTEL service.yaml structure
   - Decide: Does FR-6 create `services/otel/service.yaml` (new), or does it reference the existing `services/otel/observability/service.yaml`?
   - Update TASK-013 acceptance criteria to reflect decision
   - Verify `parse-registry.sh` will correctly discover all variants

2. **Resolve BLOCKER-2**: Apply `friday-collector` to `think` profile
   - Update `services/profiles.yaml` to include `friday-collector` in `think` profile
   - This is TASK-010 and is a blocker for smoke testing (US-1, SC-1)

3. **Clarify FR-16**: Formalize sonic health endpoint change
   - Either add to spec.md as FR-16, or confirm TASK-012 should handle this update

### SHOULD FIX (Before Kickoff)

4. **Add Phase labels to tasks.md**
   - Mark each task with `[PHASE-N]` to clarify execution order
   - Mark TASK-040 as `[SEQUENTIAL]` to prevent premature execution

5. **Expand TASK-014 acceptance criteria**
   - Add `timeout: 60` and `depends_on: []` as required fields
   - Verify against actual `services/otel/telemetry/service.yaml`

6. **Add shell script standards**
   - Extend all 5 script tasks (T020-T024) acceptance criteria to include docstring and comment guidelines per Constitution Principle V

### NICE TO HAVE (Future)

7. **Clarify startup time target**
   - Revise NFR-3 to distinguish between cold-start (first-run pull + build) and warm-cache scenarios
   - Document timeout overrides for CI/slow environments

8. **Formalize `dev-regen` target**
   - Either add to spec.md FR list or remove from plan.md

---

## Test Coverage Assessment

| Area | Spec Section | Test Method | Risk |
|------|---|---|---|
| prereqs checking | US-5, FR-5 | Manual: stop Docker, run `make dev-prereqs` | LOW (simple shell checks) |
| yaml parsing | FR-1, FR-2 | Manual: verify `.make/` output variables | MEDIUM (awk parsing fragile) |
| topological sort | FR-3, US-3 | Manual: inject circular dep, verify exit 1 | MEDIUM (DFS corner cases) |
| health polling | FR-4, US-1 | Manual: kill a service, verify timeout message | LOW (curl + timeout are standard) |
| profile selection | US-2 | Manual: `make dev PROFILE=reason` + verify SigNoz | LOW (profile selection is simple) |
| backward compat | NFR-5, SC-6 | Manual: `make flash-up`, `make otel-up` still work | MEDIUM (Make target interference) |
| integration | US-1, SC-1 to SC-9 | Manual: full `make dev && make dev-health` | **HIGH** (cross-service coordination) |

**Recommendation**: Add pre-implementation test plan to `specs/004-dev-setup/.work-docs/test-plan.md`:
- Unit tests for each shell script (awk parsing, topological sort, health polling)
- Integration test covering all 9 success criteria
- Backward compatibility matrix for existing Make targets

---

## Summary

**Status**: Ready for implementation with **2 critical blockers** to resolve.

**Blockers**:
1. BLOCKER-1: OTEL service metadata structure unclear
2. BLOCKER-2: `friday-collector` not yet in `think` profile

**Warnings**: 4 (task ordering, timeout fields, scope clarity, cold-start timing)

**Observations**: 5 (dev-regen target, network coupling, startup time, comment standards, FR-16 phantom)

**Constitution**: ✓ COMPLIANT (7/7 applicable principles pass)

**Recommendation**: **PAUSE IMPLEMENTATION** until BLOCKER-1 and BLOCKER-2 are resolved. All other gaps are minor and can be addressed during implementation sprints.

---

**Report Generated**: 2026-02-28  
**Audit Scope**: spec.md, plan.md, tasks.md, constitution.md, patterns.md, actual codebase structure  
**Next Step**: Team review of blockers; resolve via spec amendments before kicking off TASK-001
