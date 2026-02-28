# Analysis Report: 006-platform-control
**Date:** 2026-02-28
**Stage:** Pre-implementation
**Auditor:** Claude Code (read-only)

---

## Executive Summary

The 006-platform-control feature is **READY FOR IMPLEMENTATION** with **3 blockers** that must be resolved before development starts. All core patterns are sound; issues are procedural/organizational rather than architectural.

**Status**: PAUSE TO FIX BLOCKERS

- Blockers: 3
- Warnings: 4
- Observations: 3

---

## 1. BLOCKERS (Must resolve before implementing)

### 1.1 Cross-Spec Database Conflict: TASK-013 Creates Unleash DB Init Script

**Issue**: TASK-013 (`services/flags/` — Mystique) explicitly states:

> "Oracle init SQL: create `services/persistence/initdb/002_create_unleash_db.sql` containing `CREATE DATABASE unleash;`"

**Problem**: This modifies `services/persistence/initdb/`, which is **owned by spec 005-data-layer** (completed). TASK-013 has:
- Module: `services/flags/`, `services/persistence/initdb/`
- Two separate module paths that cross specification boundaries

**Compliance**: Constitution **Principle III (Modular Services)** requires each service self-contained. Mystique depends on Oracle, but **Mystique's tasks should not create files in Oracle's directory structure**.

**Root Cause**: Mystique's `DATABASE_URL=postgresql://arc:arc@arc-oracle:5432/unleash` expects an `unleash` database. The init SQL must exist, but who owns it?

**Recommendation**: 
- **Option A** (Preferred): Add a task **TASK-014** to 005-data-layer to retroactively create `002_create_unleash_db.sql` as a dependency for 006. This keeps database initialization in 005.
- **Option B**: Move `002_create_unleash_db.sql` creation to a post-005, pre-006 coordination task.
- **Option C**: Document that Mystique's Dockerfile/entrypoint script must create the database on first boot if it doesn't exist (upstream Unleash capability).

**Action**: Update plan.md and tasks.md to clarify ownership of the init SQL file before implementation.

---

### 1.2 Profiles.yaml Missing Existing Services in Updated Sections

**Issue**: Current `services/profiles.yaml` (from 005-data-layer implementation):

```yaml
think:
  services:
    - flash
    - sonic
    - strange
    - friday-collector
    - cortex
    - oracle
    - cerebro

reason:
  services:
    - cortex
    - flash
    - strange
    - sonic
    - otel
    - tardis
```

**Task TASK-001 (Spec 006) states**:
- Add `heimdall` to `think.services`
- Add `nick-fury`, `mystique` to `reason.services`

**Problem**: Current profiles.yaml is **incomplete**:
- `think` is missing `friday-collector` (it's there but let's verify the full list)
- `reason` is missing any reference to `friday` (should it be `friday` or `otel`?)

**Actual Issue**: Line 13 in current profiles.yaml shows `friday-collector`, not just `friday`. But TASK-001 acceptance doesn't validate the **full state of both profiles**, only that the three new services are added.

**Recommendation**: 
- **Update TASK-001 acceptance criteria** to verify the full list of services in each profile after the update (not just grep for presence of the three new ones).
- Ensure `friday-collector` and `otel` are correctly named in reason profile.

---

### 1.3 Missing Reviewer Verification Task (TASK-999) Acceptance Criteria

**Issue**: TASK-999 (Reviewer) references "plan.md Reviewer Checklist" but that section:
- ✓ Exists in plan.md (line 357–381)
- ✗ Is **not cross-linked** in tasks.md acceptance

**Problem**: The reviewer agent needs to know which file to check. Currently:
```markdown
[TASK-999] Acceptance (reviewer runs all items from plan.md Reviewer Checklist):
```

This assumes the reviewer knows to open `plan.md` and find line 357. If TASK-999 is in a separate agent context, the checklist won't be visible.

**Recommendation**: 
- Copy the **full reviewer checklist from plan.md into TASK-999 acceptance criteria** in tasks.md
- OR: Add an explicit reference: "See plan.md lines 357–381: Reviewer Checklist"
- This ensures the reviewer agent has all criteria in one place without context switching.

---

## 2. WARNINGS (Should address)

### 2.1 Constitution Principle VIII (Security by Default) — Nick Fury Root Deviation

**Issue**: Nick Fury (OpenBao) runs as root in dev mode. Constitution **Principle VIII** states:

> "Non-root containers (all Dockerfiles)"

Plan.md addresses this at lines 127–141:

```
# openbao/openbao runs as root by default.
# Nick Fury uses -dev mode (in-memory, auto-unsealed, known root token).
# This is a DEVELOPMENT-ONLY service. Root is acceptable for dev-mode OpenBao.
```

**Assessment**: 
- ✓ Documented in Dockerfile
- ✓ Justified in plan.md (development-only, intentional)
- ✓ Marked in Constitution Check table (line 276) as `PASS†` with footnote

**Warning (not blocker)**: The footnote at line 282 states:

> "Nick Fury root deviation is intentional — OpenBao `-dev` mode is by-design insecure."

This is **correct reasoning** but relies on external context (dev-mode semantics). If a reviewer unfamiliar with OpenBao reads this, they might flag it as a violation.

**Recommendation**: 
- Add a **REQUIRED** line to TASK-012 acceptance criteria: 
  > "Dockerfile includes comment explaining root deviation: 'OpenBao dev mode is inherently insecure and stateless. This service is development-only.'"
- Ensures every implementation artifact (not just plan.md) carries the justification.

---

### 2.2 Profiles.yaml Update Not in TASK-001 Acceptance Criteria (Detail)

**Issue**: TASK-001 updates `services/profiles.yaml` but acceptance criteria only verify presence via grep:

```
- `grep "heimdall" services/profiles.yaml` matches a line under `think.services`
- `grep "nick-fury" services/profiles.yaml` matches a line under `reason.services`
```

**Problem**: `grep` matches anywhere. If someone adds `heimdall` to a comment instead of the YAML key, grep passes. Acceptance should be stricter.

**Recommendation**: 
- Add: `python3 -c "import yaml; p = yaml.safe_load(open('services/profiles.yaml')); assert 'heimdall' in p['think']['services']"` 
- Ensures the values are in the correct YAML structure, not just text matches.

---

### 2.3 Missing [TASK-9XX] Documentation/Links Update Task Reference

**Issue**: Spec 006 includes a "Docs & Links Update" section (spec.md lines 211–217):

```markdown
## Docs & Links Update

- [ ] Update `services/profiles.yaml` — heimdall → `think`; nick-fury + mystique → `reason`
- [ ] Update `CLAUDE.md` monorepo layout to reference `gateway/`, `secrets/`, `flags/` directories
- [ ] Update `CLAUDE.md` Service Codenames table — Nick Fury: Infisical → OpenBao
- [ ] Update `.specify/config.yaml` `secrets` entry — change tech from `infisical` to `openbao`
- [ ] Verify `services/flags/service.yaml` `depends_on` lists `oracle` and `sonic`
```

But in tasks.md:
- ✓ TASK-900 exists (line 230–239) covering docs updates
- ✓ Acceptance criteria are clear

**However**: TASK-900 acceptance does NOT reference CLAUDE.md service names table update explicitly. It says:

```
- `CLAUDE.md` monorepo layout section references `gateway/`, `secrets/`, `flags/` directories
- `CLAUDE.md` Service Codenames table updated: Nick Fury row shows `OpenBao` (not `Infisical`)
```

This is fine, but the parallel spec.md list also mentions `.specify/config.yaml` update, which TASK-900 **does** include. Just verify alignment.

**Recommendation**: 
- ✓ Current state is acceptable (both spec.md and tasks.md mention it)
- Cross-reference them in a comment if unsure.

---

### 2.4 Mystique Database Migration Start Period (30s) — Risk Underspecified

**Issue**: Plan.md (line 181) states:

```
start_period: 30s   # Unleash runs DB migrations on first boot — needs longer start_period
```

And TASK-013 acceptance specifies `start_period 30s` but does NOT specify:
- What happens if Oracle is not ready? (Mentioned in edge cases, but not acceptance.)
- What if migration takes >30s? (Documented as acceptable risk in plan.md line 391, but not in task acceptance.)

**Assessment**: 
- ✓ Documented in plan.md risks
- ✓ Health check timeout is independent (5s) so continuous retries will eventually succeed
- ~ Task acceptance could be more explicit about expected behavior

**Recommendation**: 
- Add to TASK-013 acceptance: 
  > "If Mystique fails to start, logs must show DB migration in progress; `make mystique-health` retries for 30s before final health check timeout at 10s retries; migration typically completes in 10-20s."
- Clarifies expected startup delay and debugging approach.

---

## 3. OBSERVATIONS (Nice to know)

### 3.1 Heimdall Port Binding (127.0.0.1:80) Requires Root Escalation

**Issue**: Spec.md and plan.md specify:

```
ports:
  - "127.0.0.1:80:8080"     # host:80 → container proxy (non-privileged inside)
```

Port 80 is privileged (< 1024). Even with `127.0.0.1` binding, the Docker host must have privilege to bind the host port.

**Context**: 
- Plan.md (lines 59–68) explains the workaround: internal Traefik entrypoint runs on `:8080` (non-privileged), host binding is handled by Docker (which typically runs as root or with CAP_NET_BIND_SERVICE).
- This is correct and documented.

**Observation** (not a blocker):
- On some systems (e.g., rootless Docker), port 80 binding may fail with "Permission denied".
- Users with non-standard Docker configs may need to change the host port.

**Recommendation**: 
- Add to `heimdall-help` output: "Note: Port 80 binding requires Docker privilege. If startup fails with 'permission denied', override in docker-compose override or change to a higher port."

---

### 3.2 CI Pipeline Amd64-Only (Not Multi-Platform in Images Build)

**Issue**: TASK-031 (control-images.yml) specifies:

```
platforms: linux/amd64
```

But TASK-032 (control-release.yml) specifies:

```
platforms: linux/amd64,linux/arm64
```

**Assessment**: 
- ✓ Mirrors data-images.yml pattern (amd64 CI, multi-platform releases)
- ✓ Documented and intentional (plan.md line 145: "amd64 only in CI"; release multiplatform at line 237)

**Observation**: CI builds are faster (amd64 only, no QEMU), releases are portable. This is **correct** but adds complexity for multi-architecture testing.

**Recommendation**: 
- If a future task requires testing on ARM64, add a separate workflow (e.g., `control-images-multiplatform.yml`) that runs on manual trigger only.

---

### 3.3 No Persistent Volume for Nick Fury — Stateless by Design

**Issue**: Plan.md (line 30) and TASK-012 acceptance state:

```
no volume (stateless dev); health fails until Oracle is healthy
```

And TASK-012 explicitly notes:

```
No volume declared (Nick Fury is stateless in dev — data lost on restart is expected and documented)
```

**Assessment**: 
- ✓ Correct for dev mode
- ✓ Documented in plan.md risks (line 389)
- ✓ Acceptance includes verification: `no `arc-nick-fury-*` volumes`

**Observation**: This is appropriate for a dev-only service, but if a future spec wants to support persistent secrets in dev (e.g., for multi-session testing), a volume will need to be added. The current design is correct but inflexible.

**Recommendation**: 
- Document in CLAUDE.md under "Nick Fury" codename:
  > "Dev mode only — all secrets lost on restart. For persistent secrets, a future spec will add Raft-backed storage."

---

## 4. REQUIREMENTS → PLAN → TASKS COVERAGE MATRIX

| ID | Title | Applies to | Plan Section | Task(s) | Status |
|----|-------|-----------|--------------|---------|--------|
| FR-1 | Create `services/gateway/` with Traefik v3 | Heimdall | Arch § Heimdall | TASK-011, TASK-021 | ✓ |
| FR-2 | Create `services/secrets/` with OpenBao | Nick Fury | Arch § Nick Fury | TASK-012, TASK-022 | ✓ |
| FR-3 | Create `services/flags/` with Unleash | Mystique | Arch § Mystique | TASK-013, TASK-023 | ✓† |
| FR-4 | Heimdall port binding 80 + 8090 | Heimdall | Arch § Heimdall | TASK-011, TASK-021 | ✓ |
| FR-5 | Nick Fury dev mode, root token | Nick Fury | Arch § Nick Fury | TASK-012, TASK-022 | ✓ |
| FR-6 | Mystique DATABASE_URL + REDIS connection | Mystique | Arch § Mystique | TASK-013, TASK-023 | ✓† |
| FR-7 | Update profiles.yaml | Profiles | Arch § 7 | TASK-001 | ✓ |
| FR-8 | Create control-images.yml CI | CI | CI pattern § | TASK-031 | ✓ |
| FR-9 | Create control-release.yml | CI | CI pattern § | TASK-032 | ✓ |
| FR-10 | Create services/control.mk | Make | Aggregate § control.mk | TASK-024 | ✓ |
| FR-11 | Include .mk files in root Makefile | Makefile | Aggregate § | TASK-024 | ✓ |
| NFR-1 | Docker socket read-only (Heimdall) | Heimdall | Arch § Heimdall | TASK-011 | ✓ |
| NFR-2 | Nick Fury stateless (documented) | Nick Fury | Arch § Nick Fury | TASK-012 | ✓ |
| NFR-3 | All ports 127.0.0.1 only | All | Network § | TASK-011, TASK-012, TASK-013 | ✓ |
| NFR-4 | Non-root user verification | All | Arch § Non-root | TASK-011, TASK-012, TASK-013 | ✓† |
| NFR-5 | OCI + arc labels | All | Arch § File pattern | TASK-011, TASK-012, TASK-013 | ✓ |
| NFR-6 | Mystique depends_on oracle + sonic | Mystique | Arch § Mystique | TASK-013 | ✓ |
| NFR-7 | CI build < 3 minutes (amd64) | CI | CI pattern § | TASK-031 | ✓ |

Legend:
- ✓ = Coverage found and adequate
- ✓† = Coverage found but with conditional success (edge case documented)
- ✗ = Missing coverage

---

## 5. PARALLEL EXECUTION OPPORTUNITIES

Current task DAG (tasks.md lines 21–45) identifies:

**Phase 2 (Parallel)**:
- TASK-011 [P] services/gateway/ (Heimdall)
- TASK-012 [P] services/secrets/ (Nick Fury)
- TASK-013 [P] services/flags/ (Mystique)

**Phase 3 (Parallel, depends on Phase 2)**:
- TASK-021 [P] heimdall.mk
- TASK-022 [P] nick-fury.mk
- TASK-023 [P] mystique.mk

**Phase 4 (Parallel, depends on TASK-024)**:
- TASK-031 [P] control-images.yml
- TASK-032 [P] control-release.yml

**Opportunity**: All tasks marked [P] are safe to spawn in parallel. Total span (critical path):

```
TASK-001 (1) → TASK-011/012/013 (2) → TASK-021/022/023 (1)
            → TASK-024 (1) → TASK-031/032 (2) → TASK-041 (1) → TASK-900 (1) → TASK-999 (1)
```

**Critical path**: 10 units (TASK-001, 011, 021, 024, 031, 041, 900, 999 sequential; 012, 013, 022, 023, 032 parallel inside their phases).

Parallelization is **well-optimized**. No improvements needed.

---

## 6. CONSTITUTION COMPLIANCE CHECK

Cross-reference against `.specify/memory/constitution.md` v2.2.0:

| # | Principle | Applies | Status | Evidence | Issue |
|---|-----------|---------|--------|----------|-------|
| I | Zero-Dep CLI | n/a | n/a | No CLI changes | none |
| II | Platform-in-a-Box | YES | PASS | `make control-up` boots all 3; heimdall in think | none |
| III | Modular Services | YES | PASS† | Each self-contained, but Mystique's init SQL in Oracle dir | **Blocker 1.1** |
| IV | Two-Brain | YES | PASS | Config-only images; no language concern | none |
| V | Polyglot Standards | YES | PASS | Matches 003/005 patterns (Dockerfile, compose, .mk, CI) | none |
| VI | Local-First | n/a | n/a | CLI only | none |
| VII | Observability | YES | PASS | Health endpoints; Traefik dashboard; metrics available | none |
| VIII | Security | YES | WARN | Non-root attempts (Heimdall uid 1000, Mystique uid 1000) but Nick Fury root documented | **Warning 2.1** |
| IX | Declarative | n/a | n/a | CLI only | none |
| X | Stateful Ops | n/a | n/a | CLI only | none |
| XI | Resilience | YES | PASS | Health checks, start_period, Mystique depends_on oracle+sonic | none |
| XII | Interactive | n/a | n/a | CLI only | none |

**Constitution Status**: PASS with one documented deviation (Nick Fury root, justified for dev-only).

---

## 7. SERVICE PATH VALIDATION

Cross-reference module paths against `services/profiles.yaml` and actual directories:

| Service | Path | Exists? | Profile | Status |
|---------|------|---------|---------|--------|
| arc-heimdall | `services/gateway/` | N (to-be-created) | think | ✓ |
| arc-nick-fury | `services/secrets/` | N (to-be-created) | reason | ✓ |
| arc-mystique | `services/flags/` | N (to-be-created) | reason | ✓ |
| arc-oracle | `services/persistence/` | Y (existing) | think | ✓ |
| arc-sonic | `services/cache/` | Y (existing) | think | ✓ |

All paths are **valid and follow the pattern** from spec 005-data-layer.

---

## 8. UNDEFINED/UNTESTABLE ACCEPTANCE CRITERIA

Scan tasks.md for vague or untestable criteria:

| Task | Criterion | Issue | Recommendation |
|------|-----------|-------|-----------------|
| TASK-011 | "if `USER 1000` causes Traefik to fail at runtime, remove `USER 1000` and document" | Vague — how to test? | Add explicit test: `docker run --rm ghcr.io/arc-framework/arc-heimdall:latest traefik version` must succeed |
| TASK-012 | "if `wget` absent in openbao image, fall back to bash `/dev/tcp`" | Untestable in acceptance — error handling is conditional | Add: "Test both wget and /dev/tcp patterns; CI will verify which is available" |
| TASK-013 | "if Unleash fails to start, remove and add comment" | Conditional acceptance — implies retry loop | Add: "If uid 1000 fails, document root deviation + justification in compose comments; verify startup logs" |
| TASK-024 | "all three health targets; exits non-zero if any fails" | Testable but needs explicit command | Add: "`make control-health` and verify exit code via `echo $?` is 0" |

**Recommendation**: Update tasks.md acceptance for TASK-011, TASK-012, TASK-013 to include explicit fallback testing procedures.

---

## 9. DANGEROUS PATTERNS & RISKS

### 9.1 Mystique Creates Unleash DB (BLOCKER 1.1 — Covered Above)

### 9.2 Nick Fury Root — Needs Explicit Sign-Off

Currently marked as acceptable for dev-only, but reviewers may challenge. Recommend adding explicit **approval gate** in TASK-999.

### 9.3 Port 80 Binding on Unprivileged Systems

Heimdall requires privilege to bind port 80. If Docker is rootless, this will fail. Not a blocker but should be documented in a `heimdall-help` note.

---

## 10. MISSING TASKS / GAPS

### Potential Missing Tasks

| Gap | Spec Impact | Suggested Task |
|-----|-------------|-----------------|
| Unleash default admin credentials setup | US-4 (Mystique starts and serves UI) | Add post-startup task to retrieve auto-generated credentials from Unleash logs |
| Traefik dashboard access verification | US-2 (Heimdall auto-discovers services) | Implicit in E2E (TASK-041); no separate task needed |
| OpenBao secret backend initialization | US-3 (Nick Fury dev mode) | Implicit in health check; no task needed (stateless dev) |
| Mystique feature flag seeding | Not in scope | Future spec (post-launch data population) |

**Assessment**: No critical missing tasks. All user stories have corresponding tasks.

---

## FINAL ASSESSMENT

**Recommendation**: PAUSE TO FIX BLOCKERS

### Must Resolve Before Implementation:

1. **Blocker 1.1**: Clarify ownership of `services/persistence/initdb/002_create_unleash_db.sql`
   - Action: Update plan.md and TASK-013 to reference a coordination task or document Unleash's built-in DB creation capability.
   
2. **Blocker 1.2**: Verify profiles.yaml completeness in TASK-001 acceptance
   - Action: Update TASK-001 acceptance to validate full profile structure (not just grep).

3. **Blocker 1.3**: Copy reviewer checklist into TASK-999 acceptance criteria
   - Action: Embed the full checklist from plan.md into tasks.md TASK-999 section.

### Should Address Before Implementation:

4. **Warning 2.1**: Add explicit Dockerfile comment requirement for Nick Fury root deviation to TASK-012.
5. **Warning 2.2**: Strengthen TASK-001 YAML validation (use Python YAML parser, not grep).
6. **Warning 2.3** (already addressed): Verify .specify/config.yaml update is in scope.
7. **Observation 3.1**: Add heimdall-help note about port 80 privilege requirement.
8. **Observation 3.2**: Clarify Mystique startup delay expectations in TASK-013 acceptance.

### Timeline

- **Fix blockers**: 15–20 minutes (mostly rewording and cross-linking)
- **Address warnings**: 10 minutes (minor acceptance criterion updates)
- **Implementation**: Ready after blockers resolved

---

## APPENDIX: Detailed Task Dependencies

```mermaid
graph TD
    T001["TASK-001\n1 unit\nprofiles.yaml"] 
    
    T011["TASK-011 [P]\n2 units\ngateway/"]
    T012["TASK-012 [P]\n2 units\nsecrets/"]
    T013["TASK-013 [P]\n2 units\nflags/"]
    
    T021["TASK-021 [P]\n1 unit\nheimdall.mk"]
    T022["TASK-022 [P]\n1 unit\nnick-fury.mk"]
    T023["TASK-023 [P]\n1 unit\nmystique.mk"]
    
    T024["TASK-024\n1 unit\ncontrol.mk + Makefile"]
    
    T031["TASK-031 [P]\n2 units\ncontrol-images.yml"]
    T032["TASK-032 [P]\n2 units\ncontrol-release.yml"]
    
    T041["TASK-041\n1 unit\nE2E verification"]
    
    T900["TASK-900 [P]\n1 unit\nDocs & links"]
    T999["TASK-999\n1 unit\nReviewer"]
    
    T001 --> T011
    T001 --> T012
    T001 --> T013
    
    T011 --> T021
    T012 --> T022
    T013 --> T023
    
    T021 --> T024
    T022 --> T024
    T023 --> T024
    
    T024 --> T031
    T024 --> T032
    
    T031 --> T041
    T032 --> T041
    
    T041 --> T900
    T041 --> T999
    T900 --> T999
    
    style T001 fill:#e1f5ff
    style T041 fill:#fff9c4
    style T999 fill:#f3e5f5
```

**Critical Path** (longest dependency chain):
TASK-001 → TASK-011 → TASK-021 → TASK-024 → TASK-031 → TASK-041 → TASK-900 → TASK-999 = **10 units**

**Parallelizable units**:
- TASK-011, TASK-012, TASK-013 (Phase 2): 6 units in parallel
- TASK-021, TASK-022, TASK-023 (Phase 3): 3 units in parallel
- TASK-031, TASK-032 (Phase 4): 4 units in parallel

**Total effort** (critical path only, sequential): 10 units
**With parallelization** (realistic wall-clock time): ~6 units (Phase 1: 1, Phase 2 parallel: 2, Phase 3 parallel: 1, Phase 4 parallel: 2, Phase 5: 1 sequential)

