# Analysis Report: 005-data-layer

**Date:** 2026-02-28  
**Stage:** Pre-implementation  
**Auditor:** Claude Code (read-only analysis)

---

## CRITICAL BLOCKERS

### 1. config.yaml Path Mismatch: References `search/` Instead of `vector/`

**Issue:** Canonical SSOT (config.yaml) registers Cerebro at `services/search/`, but spec, plan, and most task content use `services/vector/`:

**config.yaml L41 (current):**
```yaml
- { dir: "search", codename: "cerebro", tech: "qdrant", lang: "config" }
```

**Spec/Plan/Tasks intent:**
- **spec.md L13, L58:** `services/vector/`
- **plan.md L15, L102:** `services/vector/`
- **tasks.md L87, L125 (TASK-012, TASK-022):** `services/search/` — tasks note this mismatch on L19

**Risk Level:** CRITICAL — If config.yaml is not updated to match `services/vector/`, service discovery tools and any automation reading config.yaml will fail.

**Action Required:** Update **config.yaml L41** before implementation:
```yaml
- { dir: "vector", codename: "cerebro", tech: "qdrant", lang: "config" }
```

---

### 2. profiles.yaml Missing All Three New Services

**Issue:** Spec requires FR-7 and TASK-001 to register oracle, cerebro, and tardis in profiles, but current profiles.yaml has none:

**Current state (as of 2026-02-28):**
```yaml
think:
  services:
    - flash
    - sonic
    - strange
    - friday-collector
    - cortex
  # MISSING: oracle, cerebro

reason:
  services:
    - cortex
    - flash
    - strange
    - sonic
    - otel
  # MISSING: tardis
```

**Spec requirements:**
- **spec.md FR-7:** Add oracle + cerebro to `think`; tardis to `reason`
- **tasks.md TASK-001 AC (L66-69):** Verify profiles updated and `make dev` works

**Risk:** If profiles.yaml is not updated before TASK-011/012/013 create the service directories, `make dev --profile think` will fail to wire oracle and cerebro, breaking the "Platform-in-a-Box" principle (Constitution II).

**Action Required:** Update profiles.yaml before or as part of TASK-001:

```yaml
think:
  services:
    - flash
    - sonic
    - strange
    - friday-collector
    - cortex
    - oracle       # ADD
    - cerebro      # ADD

reason:
  services:
    - cortex
    - flash
    - strange
    - sonic
    - otel
    - tardis       # ADD
```

---

### 3. TASK-001 Acceptance Criteria Too Weak for Verification

**Issue:** TASK-001 AC does not enforce that oracle/cerebro/tardis codenameactually appear in profiles.yaml:

**Current AC (tasks.md L66-69):**
```
- `think.services` list includes `oracle` and `cerebro` (by codename)
- `reason.services` list includes `tardis` (by codename)
```

This is stated as desired outcome, but acceptance criteria should be testable shell commands:

**Example of testable criteria:**
```
- grep -q "oracle" services/profiles.yaml && grep -q "cerebro" services/profiles.yaml
- grep "reason:" -A 10 services/profiles.yaml | grep -q "tardis"
- YAML parses without error: `docker compose -f services/docker-compose.yml config >/dev/null`
```

**Action Required:** Update TASK-001 acceptance to include explicit test commands or checklist items.

---

## WARNINGS

### 4. Tasks.md Still References `services/search/` — Inconsistent Update Needed

**Issue:** tasks.md line 19 explicitly flags the mismatch, suggesting it was a known inconsistency during planning:

**tasks.md L19:**
```
> **Directory note**: `config.yaml` maps Cerebro/Qdrant to `services/search/` (not `vector/`). 
> Tasks use the config-authoritative path.
```

However, decision was made to proceed with `services/vector/` in spec/plan. Tasks should be updated to be consistent:

**Affected task lines:**
- L30: `T012["TASK-012 [P]\nservices/search/\nCerebro"]` → should be `services/vector/`
- L87: TASK-012 module = `services/search/` → should be `services/vector/`
- L125: TASK-022 module = `services/search/` → should be `services/vector/`
- L156: Makefile include path → should reference `services/vector/cerebro.mk`

**Action Required:** Update tasks.md to use `services/vector/` everywhere; remove the disclaimer on L19.

---

### 5. MinIO Non-Root User — Decision Path Unclear

**Issue:** plan.md discusses Option A vs. Option B (L168-174) but does not finalize the approach:

**plan.md L173:**
```
If neither works with the upstream image, document the root deviation in docker-compose.yml comments (same as Pulsar in 003).
```

**Problem:**
- No indication which option will be attempted first
- TASK-013 acceptance criteria (tasks.md L100-105) does not require uid verification
- Constitution Principle VIII (Security) requires non-root, but fallback is documentation-only

**Action Required:** Update TASK-013 acceptance to explicitly verify:
```
- Option A attempted: user: "1000:1000" in docker-compose with /data permissions
- If Option A fails, Option B attempted (Dockerfile + USER directive)
- If both fail, uid confirmed at runtime AND deviation documented in comment with explicit rationale
- docker inspect arc-tardis | jq '.[0].Config.User' returns non-root uid or has comment explaining deviation
```

---

### 6. NFR-6 CI Build Time Requirement Not Validated

**Issue:** Spec NFR-6 (L134) and SC-5 (L197) require "CI build completes in under 3 minutes (amd64 only; no QEMU)":

**Problem:**
- No baseline performance data provided
- Docker image pull time for postgres:17-alpine and qdrant/qdrant not measured
- Success criteria fails immediately if amd64 build exceeds 3 minutes on first run
- No tuning strategy or fallback in plan

**Recommendation:** Either:
- Remove the 3-minute hard requirement and make it a performance target
- Add a task to baseline CI runner performance before declaring success
- Or defer to v0.2.0 after observing actual build times

**Action:** Update SC-5 acceptance in TASK-031 to include baseline measurement.

---

### 7. Cortex Health Check Integration Not Tested

**Issue:** SC-2 (L194-195) requires Cortex `/health/deep` to report `oracle: ok`, but:
- No verification that Cortex code changes are needed
- No indication of which task handles Cortex integration (not in 005-data-layer scope)
- TASK-041 acceptance (L212) assumes cortex will be ready, but startup order unclear

**Recommendation:** Add a clarification to TASK-041 or plan:
```
Prerequisite: Cortex has been separately updated to probe oracle service 
(may be out-of-scope for this spec; verify in TASK-041)
```

---

### 8. TASK-900 Docs Update — Vague Acceptance Criteria

**Issue:** TASK-900 (L218-227) references cortex service.yaml update but does not verify it exists or is in scope:

**Current AC:**
```
- `services/cortex/service.yaml` `depends_on` field references `oracle` codename (add if missing)
```

**Problem:**
- Does `cortex/service.yaml` exist?
- Is updating cortex's depends_on within 005-data-layer scope, or a separate issue?
- CLAUDE.md reference is vague ("add if missing")

**Action Required:** Verify cortex/service.yaml exists and clarify whether update is in-scope or deferred.

---

### 9. Tech Debt Items Not Scheduled for Revisit

**Issue:** plan.md lists three tech debt items (L333-338) with no follow-up task:

**TD-001:** Qdrant Prometheus scraping  
**TD-002:** MinIO Prometheus scraping  
**TD-003:** Default bucket creation

**Problem:** No mechanism to track reopening these; risks orphaning them post-merge.

**Recommendation:** Either create a separate GitHub issue for observability integration, or add a comment in the respective .mk files referencing the debt items.

---

## OBSERVATIONS

### 10. Constitution Compliance — Principle VII (Observability) Incomplete

**Issue:** plan.md marks Principle VII as "PASS" (L85), but observability integration is deferred:

**Current state:**
- Health checks: Implemented (pg_isready, /readyz, /health/live)
- OTEL instrumentation: Deferred (TD-001, TD-002 for Prometheus scraping)
- SigNoz dashboards: Not mentioned

**Analysis:** Health checks satisfy the baseline observability requirement. OTEL integration is acceptable tech debt per plan rationale (L85). This is compliant as-is.

---

### 11. Parallel Task Safety Confirmed — But Contingent on Path Resolution

**Issue:** Dependency graph shows maximum parallelism (9/13 tasks parallel), but contingent on blocker #1:

**If config.yaml is updated to `services/vector/`:**
- TASK-011, 012, 013 have no file conflicts → fully parallel
- TASK-021, 022, 023 have no file conflicts → fully parallel after Phase 2
- TASK-031, 032 independent → parallel

**Current risk:** If tasks.md is not updated to `services/vector/`, parallel execution will create files in wrong directories.

---

### 12. No Container Build Context Validation

**Issue:** Tasks do not explicitly verify Dockerfile context path:

**Suggested acceptance for TASK-011/012/013:**
```
- docker build succeeds from repo root:
  docker build -f services/persistence/Dockerfile -t test-oracle services/persistence/
- (repeat for vector/ and storage/)
```

Currently implied but not explicit.

---

### 13. Network Lifecycle Not Documented

**Issue:** spec mentions `arc_platform_net` must exist (L187), but:
- No documentation of which `make` target creates it
- TASK-024 ensures `data-up` creates it if missing (`docker network create arc_platform_net 2>/dev/null || true`)
- But no guidance on lifecycle if network is manually deleted post-init

**Recommendation:** Add comment to data.mk explaining network creation logic.

---

### 14. Edge Case: Oracle Password Post-Init

**Issue:** spec L188 notes "Postgres ignores `POSTGRES_PASSWORD` after data dir is initialized":

**This is documented correctly, but:**
- No guidance in TASK-021 on how to handle re-initialization
- Users may try to change password via env vars and get silent failure

**Suggestion:** Add note to oracle.mk help text about password reset requiring `oracle-nuke`.

---

### 15. Service Health Check Start Periods Differ

**Issue:** spec L130 specifies different start_periods per service, but rationale not explained:

| Service | Start Period | Rationale |
|---------|--------------|-----------|
| Oracle | 10s | Postgres slow to initialize |
| Cerebro | 5s | Qdrant quick to boot |
| Tardis | 5s | MinIO quick to boot (per plan L256) |

Currently correct, but spec should explain why Oracle is 2x slower. This helps implementers adjust if upstream image changes.

---

## COVERAGE MATRIX

| Requirement | Type | Task ID(s) | Status |
|-------------|------|-----------|--------|
| FR-1: persistence/ Dockerfile + files | FR | TASK-011 | OK |
| FR-2: vector/ Dockerfile + files | FR | TASK-012 | BLOCKED (config.yaml) |
| FR-3: storage/ Dockerfile + files | FR | TASK-013 | OK |
| FR-4: Oracle init + volume | FR | TASK-011 | OK |
| FR-5: Cerebro volumes + ports | FR | TASK-012 | BLOCKED (config.yaml) |
| FR-6: Tardis S3 + console + volume | FR | TASK-013 | WARNING (uid) |
| FR-7: profiles.yaml update | FR | TASK-001 | BLOCKED (missing) |
| FR-8: data-images.yml CI | FR | TASK-031 | WARNING (3min SLA) |
| FR-9: data-release.yml release | FR | TASK-032 | OK |
| FR-10: data.mk aggregate | FR | TASK-024 | OK |
| FR-11: Makefile includes | FR | TASK-024 | OK |
| NFR-1: Non-root users | NFR | TASK-011, 012, 013 | WARNING (MinIO) |
| NFR-2: Health endpoints | NFR | TASK-011, 012, 013 | OK |
| NFR-3: Named volumes | NFR | TASK-011, 012, 013 | OK |
| NFR-4: 127.0.0.1 binding | NFR | TASK-011, 012, 013 | OK |
| NFR-5: OCI + arc labels | NFR | TASK-011, 012, 013 | OK |
| NFR-6: 3-minute CI SLA | NFR | TASK-031 | WARNING (untested) |
| SC-1: `make data-up` health | SC | TASK-041 | OK |
| SC-2: Cortex /health/deep | SC | TASK-041 | WARNING (not in scope) |
| SC-3: Qdrant /readyz | SC | TASK-041 | OK |
| SC-4: MinIO console | SC | TASK-041 | OK |
| SC-5: CI <3 min | SC | TASK-031 | WARNING (duplicate/untested) |
| SC-6: Release workflow | SC | TASK-032 | OK |
| SC-7: Trivy CVE scan | SC | TASK-032 | OK |
| SC-8: profiles.yaml content | SC | TASK-001, 041 | BLOCKED (missing) |

---

## RISK SUMMARY

| Risk | Severity | Mitigation | Owner |
|------|----------|-----------|-------|
| config.yaml not updated to `services/vector/` | CRITICAL | Update config.yaml L41 before TASK-012 starts | Team lead |
| profiles.yaml empty — no services registered | CRITICAL | Pre-populate or enforce TASK-001 as hard blocker | TASK-001 owner |
| TASK-001 AC too weak for verification | HIGH | Add explicit shell test commands | TASK-001 owner |
| tasks.md still references `services/search/` | HIGH | Update tasks L30, L87, L125, L156 | Plan owner |
| MinIO uid unverified | MEDIUM | Add runtime verification to TASK-013 | TASK-013 owner |
| CI 3-minute SLA untested | MEDIUM | Benchmark first run; adjust or defer | TASK-031 owner |
| Cortex integration not in scope | MEDIUM | Clarify in TASK-041 prerequisite or separate issue | Plan owner |
| Tech debt orphaned | LOW | Create GitHub issue for observability integration | Release manager |

---

## PARALLEL OPPORTUNITIES

**Current design supports maximum parallelism:**

**Phase 2 (Services):** TASK-011 (persistence), TASK-012 (vector), TASK-013 (storage) — fully parallel, no file conflicts

**Phase 3 (Make):** TASK-021, 022, 023 — parallel after Phase 2; TASK-024 — sequential after all three

**Phase 4 (CI/CD):** TASK-031 (data-images), TASK-032 (data-release) — parallel, independent

**Phase 5 (Integration):** TASK-041 — sequential after Phase 4

**Phase 6 (Polish):** TASK-900 (docs), TASK-999 (reviewer) — sequential

**Bottlenecks:** None, if blockers are resolved.

---

## CONSTITUTION COMPLIANCE

| Principle | Applies | Status | Notes |
|-----------|---------|--------|-------|
| I. Zero-Dep CLI | N/A | — | Services only |
| II. Platform-in-a-Box | YES | BLOCKED | Contingent on profiles.yaml update (blocker #2) |
| III. Modular Services | YES | OK | Each self-contained; flat under services/; own codename in config.yaml |
| IV. Two-Brain | YES | OK | Config-only; no language separation concern |
| V. Polyglot Standards | YES | OK | Dockerfiles, compose, health checks follow 003 pattern |
| VI. Local-First | N/A | — | CLI only |
| VII. Observability | YES | OK | Health checks present; Prometheus deferred as TD-001 (acceptable) |
| VIII. Security | YES | WARNING | Oracle + Cerebro confirmed non-root; MinIO uid unverified (warning #5) |
| IX. Declarative | N/A | — | CLI only |
| X. Stateful Ops | N/A | — | CLI only |
| XI. Resilience | YES | OK | Health checks + start_periods; named volumes survive restart |
| XII. Interactive | N/A | — | CLI only |

**Overall:** 6 PASS, 2 WARNING, 3 N/A

---

## SUMMARY

| Category | Count | Detail |
|----------|-------|--------|
| CRITICAL BLOCKERS | 3 | Path mismatch, missing profiles, weak AC |
| WARNINGS | 6 | Tasks consistency, uid verification, CI SLA, docs scope, tech debt, health check |
| OBSERVATIONS | 6 | Constitution VII partial, parallelism safe, build context, network lifecycle, postgres password, start periods |
| **Total Issues** | **15** | — |

### Recommendation

**PAUSE IMPLEMENTATION — FIX BLOCKERS FIRST**

**Must resolve before TASK-001 starts:**
1. Update `.specify/config.yaml` L41: change `dir: "search"` → `dir: "vector"`
2. Populate `services/profiles.yaml` with oracle, cerebro, tardis registrations (template provided in warning #2)
3. Strengthen TASK-001 acceptance criteria with testable shell commands
4. Update tasks.md to consistently use `services/vector/` (L30, L87, L125, L156)

**Should address before Phase 2 starts:**
- Update TASK-013 acceptance to verify MinIO uid
- Clarify TASK-900 scope (cortex integration — in or out of scope?)
- Adjust or defer CI 3-minute SLA to performance target

**After blockers resolved:**
- Proceed with full parallelization of Phase 2–4
- Use TASK-999 (reviewer) to validate Constitution compliance
- Track tech debt items (TD-001, TD-002, TD-003) in GitHub issues

**Estimated remediation time:** 1–2 hours. Then implementation can proceed smoothly.

---

*Report generated: 2026-02-28 by Claude Code (pre-implementation audit)*
