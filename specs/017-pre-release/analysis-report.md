# Analysis Report: 017-pre-release
**Date:** 2026-03-10  
**Stage:** Pre-implementation  
**Status:** BLOCKERS PRESENT — address before proceeding

---

## Executive Summary

The 017-pre-release feature spec, plan, and tasks are well-structured and comprehensive. However, **5 blockers and 3 warnings** must be resolved before implementation can begin. The issues fall into three categories:

1. **Task coverage gaps** — requirements without matching tasks
2. **Acceptance criteria vagueness** — some criteria lack testable specificity
3. **Phase 2 workflow dependencies** — release pipeline triggers need clarification

---

## BLOCKERS (must resolve before implementing)

### [BLOCKER-1] TASK-040 missing dependency on TASK-024
**File:** `tasks.md` line 145  
**Issue:** TASK-040 (verify `make docs-build`) lists dependencies as `TASK-020, TASK-021, TASK-022, TASK-023, TASK-024`, but the dependency graph at line 10-27 shows TASK-024 feeding into TASK-040 with no direct edge. The mermaid diagram is **incomplete** — it should show TASK-024 explicitly connected to TASK-040.

**Impact:** Task execution order ambiguity. Reviewers will be uncertain whether Makefile updates must complete before the build verification.

**Resolution:** Update the mermaid graph (lines 9-27) to explicitly show `T024 --> T040`.

---

### [BLOCKER-2] Phase 2 workflow dispatch permission gap
**File:** `plan.md` lines 214-259  
**Issue:** The plan correctly identifies that `platform-release.yml` will call `workflow_dispatch` on 8 sub-workflows via `gh workflow run`. However, it states:

> "Uses `GITHUB_TOKEN` with `actions: write` permission (available for same-repo dispatches)"

The plan lacks evidence that `GITHUB_TOKEN` has the `actions: write` scope. GitHub's default token for workflows only grants `contents: write`. Dispatching workflows in the same repo requires an explicit `actions: write` grant in the workflow's `permissions:` block.

**Acceptance criteria affected:**
- FR-P2-2: "workflow calls each service release workflow...via workflow_dispatch"
- NFR-P2-3: Implicit — that `make publish-all` will succeed

**Current plan text:** 
- Risk mitigation at line 258 says "`workflow` scope" is needed, but then contradicts itself by saying `GITHUB_TOKEN` suffices.

**Resolution:** Clarify in `platform-release.yml` task (TASK-100) acceptance criteria that:
```yaml
permissions:
  contents: write
  actions: write
```
must be explicitly set in the workflow YAML. Update the risk at line 258 to say "Mitigation: Explicitly set `permissions.actions: write` in the platform-release.yml workflow definition."

---

### [BLOCKER-3] Service list mismatch in Phase 2 requirements
**File:** `spec.md` lines 273-277 and `plan.md` line 56-77

**Issue:** The "Today — Fragmented + Incomplete" architecture diagram and current status table list **20 total expected images**, but:

1. The status table (lines 245-267) only shows **19** entries (7 published + 13 missing).
2. The Phase 2 architecture diagram (lines 313-323) only shows **8** service workflows being triggered (voice, cortex, reasoner, data, messaging, otel, realtime, control).
3. The missing `arc-sherlock` entry (line 267) is marked "delete" — so the count should be 18 (not 20).

**Breakdown mismatch:**
- 7 currently published: arc-gateway, arc-vault, arc-flags, arc-cortex, arc-sql-db, arc-friday-collector, arc-reasoner, arc-voice-agent (8, not 7)
- 13 missing listed, but only covers 8 workflow groups in Phase 2

**Root cause:** The spec conflates the 20 possible service images (if all infrastructure were split out) with the 8 coordinated release workflow groups. Not every image maps to a separate workflow; many are bundled (e.g., all Friday/OTEL images come from `otel-release.yml`).

**Impact:** Success criteria (SC-P2-3) expects "all 8 service images" in the release body, but doesn't clarify what "20 images" means or which images map to which workflows.

**Resolution:**
1. In `spec.md` Phase 2 section, add a clarification table mapping the 8 release workflows to the images each produces (e.g., "otel-release.yml produces: arc-friday, arc-friday-collector, arc-friday-clickhouse, arc-friday-migrator, arc-friday-zookeeper").
2. Update Phase 2 success criteria (lines 375-379) to specify the expected image count per workflow, not a single global count.
3. Remove or clarify the "20 expected images" claim at line 243 — document that it's the union of all possible services, not a single release coordination goal.

---

### [BLOCKER-4] US-6 (voice service docs) contradicts Phase 2 scope
**File:** `spec.md` lines 114-122

**Issue:** US-6 is listed as a **Phase 1 "Should Have"** requirement, but depends on Phase 2 deliverables:

> "When I open `services/voice.md`  
> Then I find working `curl` examples for `/v1/audio/transcriptions` and `/v1/audio/speech` with the correct port (8803)"

Voice service is currently in development (per `SERVICE.MD` line 58: "pending Makefile registration"). The curl examples cannot be verified until:
1. The voice service is integrated into the runnable platform (Phase 2 release pipeline must complete)
2. Or the spec explicitly limits US-6 to stub examples that will be verified in a future phase

**Current acceptance criteria** (line 121):
> "The STT and TTS examples match the actual FastAPI route definitions in `services/voice/src/`"

This is testable against the codebase, but the story itself assumes `curl` examples will work against a running platform — which Phase 1 does not guarantee.

**Impact:** Reviewer task (TASK-999) will fail if US-6 acceptance criteria require a running voice service, but Phase 1 does not include voice capability activation in any test profile.

**Resolution:** Either:
1. Move US-6 to Phase 2, or  
2. Split US-6: CR-6a (create stub page with route definitions) stays in Phase 1; CR-6b (verify curl examples against running service) moves to Phase 2 integration test, or  
3. Update US-6 acceptance to say "examples are extracted from FastAPI route definitions; no live service required for verification"

---

### [BLOCKER-5] TASK-101 `gh workflow run` input format unclear
**File:** `tasks.md` lines 132-138

**Issue:** TASK-101 acceptance criteria state:

> "Calls `gh workflow run platform-release.yml --ref main` with no extra args (uses manual version input)"

This is ambiguous. The `platform-release.yml` workflow has two trigger modes (lines 113-115 of plan.md):
- `on.push.tags: ['platform/v*']` — version extracted from tag
- `on.workflow_dispatch.inputs.version` — version supplied manually

The acceptance criteria says "with no extra args", but `gh workflow run` requires either:
1. The `version` input to be passed: `gh workflow run platform-release.yml -f version=v0.1.0`, or  
2. The workflow prompts for it interactively (which breaks in CI/non-interactive mode)

**Impact:** TASK-101 implementation will fail if the workflow dispatch signature doesn't match the `make publish-all` invocation.

**Resolution:** Clarify in TASK-101 acceptance criteria:

> "Calls `gh workflow run platform-release.yml -f version=v0.1.0 --ref main` (prompts user for version interactively if not provided in a CI flag; or accepts `VERSION=v0.1.0 make publish-all` to supply it)"

Also update the plan.md at line 224 to show the exact `gh workflow run` syntax with `-f` input flags.

---

## WARNINGS (should address before implementing)

### [WARNING-1] Phase 1 edge case — old docs/specs/ directory deletion
**File:** `spec.md` lines 189-196 and `tasks.md` lines 41-49

**Issue:** The edge cases section mentions "symlink broken (specs dir not present)" but the migration process doesn't explicitly document how to clean up the **old directory structure**.

The plan (line 188-197) shows:
```bash
git rm -r docs/specs/  # Delete remaining contents
ln -s ../specs docs/specs
git add docs/specs
```

However, the old `docs/specs/` contained:
- `.vitepress/` (moved)
- `package.json` (moved)
- `package-lock.json` (moved)
- `content/` symlink (to be removed)
- Potentially other files like `.gitignore`, `tsconfig.json`, etc.

**Risk:** If any files are left behind or the symlink creation fails, the build will silently include the old structure, causing VitePress to load the wrong srcDir.

**Resolution:** Update TASK-001 acceptance criteria to explicitly check:
```bash
- [ ] `git ls-tree HEAD docs/specs/` outputs only the symlink (no directory entries)
- [ ] `file docs/specs` returns "docs/specs: symbolic link to ../specs"
- [ ] No files remain in the old `docs/specs/` on disk
```

---

### [WARNING-2] Service count inconsistency between US-5 acceptance and spec.md
**File:** `spec.md` lines 107-112 and `SERVICE.MD` line 20-48

**Issue:** US-5 requires a service map page with **"all 15 services"**. However, `SERVICE.MD` lists:

**Authoritative map:** 14 services
- 13 infrastructure services (gateway, flags, vault, messaging, streaming, cache, persistence, storage, realtime, cortex, otel, friday-collector, identity planned)
- 2 full-featured services (reasoner, voice)

(The realtime "sidecars" — ingress, egress — are listed separately as runtime services under `realtime`, not as standalone entries.)

**Planned services not yet in Makefile:** 8 additional services (voice-agent, guard, critic, gym, billing, vector-db, identity, chaos) listed as "Planned, not yet in Makefile".

**Contradiction:** The spec says "all 15 platform services" but the authoritative `SERVICE.MD` only lists 14 current services, with 8 more planned for the future.

**Impact:** SC-7 success criteria (line 206) will be ambiguous: "≥ 13 service pages" passes, but the spec's promise of "all 15" may disappoint users.

**Resolution:** Update US-5 requirements (line 112) to say:

> "I can find all 14 current platform services with their port, codename, and tier membership in the table. Planned services (guard, critic, gym, etc.) are documented separately in an 'Architecture Roadmap' section if included."

Or, if the intent is to include stub pages for all planned services, update the spec to say explicitly: "all 14 active + 8 planned services" and add stubs for them to TASK-022.

---

### [WARNING-3] Constitution Principle II compliance marker imprecise
**File:** `plan.md` lines 82-84

**Issue:** The constitution compliance matrix marks Principle II (Platform-in-a-Box) as **PASS** with the note:

> "PASS | `make docs` = single command to bring up documentation surface"

However, Principle II is defined in the constitution (`.specify/memory/constitution.md` lines 28-35) as:

> "A single `docker-compose up` (or `arc run --profile think`) bootstraps a working AI agent platform."

The principle is about **the platform services**, not the documentation surface. Phase 1 adds a docs command, which is orthogonal to platform-in-a-box.

**Actual alignment:** Phase 1 does not impact the platform-in-a-box principle at all — it only affects documentation. Phase 2 could potentially impact it if the release pipeline adds new services or changes the orchestration model, but the current plan doesn't.

**Impact:** The constitution check table is misleading — it suggests the feature advances the principle when in fact it's N/A (not applicable).

**Resolution:** Update `plan.md` line 82 to:

```
| II | Platform-in-a-Box | N/A | No impact on service orchestration or profiles; docs module only |
```

---

## OBSERVATIONS (nice to know)

### [OBS-1] TASK-024 should verify Makefile help text format
**File:** `tasks.md` lines 108-117

**Observation:** TASK-024 updates the Makefile and CLAUDE.md, but the acceptance criteria don't specify the exact help comment format. The repo uses a consistent style (e.g., `## section:` with description).

**Suggestion:** Add to TASK-024 acceptance:
```
- [ ] `make help` shows a "docs:" section with description matching existing help comment style
- [ ] Help text reads: "## docs: Build and run the documentation site locally (http://localhost:5173/arc-platform/docs/)"
```

---

### [OBS-2] TASK-101 should verify workflow exists before dispatching
**File:** `tasks.md` lines 132-138

**Observation:** The acceptance criteria for TASK-101 say the target should check `gh auth status`, but they don't mention validating that `platform-release.yml` actually exists in the repo before attempting dispatch.

**Suggestion:** Add to TASK-101 acceptance:
```
- [ ] Before dispatching, verify the workflow exists: `gh workflow view platform-release.yml` exits 0
- [ ] If workflow doesn't exist, print: "platform-release.yml workflow not found — run TASK-100 first"
```

---

### [OBS-3] Symlink preservation across srcDir change not verified
**File:** `tasks.md` lines 144-152 (TASK-040)

**Observation:** TASK-040 verifies the symlink exists after build (`ls docs/specs/001-otel-setup/spec.md`), but doesn't verify that the VitePress build process correctly honored `resolve.preserveSymlinks: true`.

**Suggestion:** Add to TASK-040 acceptance:
```
- [ ] Run `grep -A2 "resolve:" docs/.vitepress/config.ts` and verify `preserveSymlinks: true` is present
- [ ] Check VitePress dist: symlink structure is preserved in `.vitepress/dist/specs/` (not flattened)
```

---

### [OBS-4] FR-7 and SC-6 do not specify exact endpoint ports for curl examples
**File:** `spec.md` lines 151, 205-206 and `tasks.md` line 74-79

**Observation:** TASK-020 requires "≥ 5 curl examples" including STT and TTS, but the spec doesn't enforce that the STT/TTS examples use port 8803 (voice service) vs. port 8802 (reasoner). The acceptance criteria at line 79 say "port 8803" for STT/TTS, which is correct, but lines 79-80 also mention "curl examples for... TTS" without emphasizing the port difference.

**Suggestion:** Clarify in TASK-020 acceptance criteria:
```
- [ ] Chat completion examples use port 8802 (reasoner service)
- [ ] STT and TTS examples use port 8803 (voice service)
- [ ] All 5+ examples explicitly show `curl -X POST http://localhost:<PORT>/...`
```

---

### [OBS-5] No task to verify `editLink.pattern` correctness
**File:** `spec.md` line 218 and `tasks.md`

**Observation:** The spec's "Docs & Links Update" section (line 218) mentions:

> "Verify that the `editLink.pattern` in `config.ts` points to the correct GitHub path after srcDir changes from `./content` to `.`"

However, TASK-900 doesn't include an explicit acceptance criterion for this. The pattern needs to handle two cases:
- `docs/**` content → `...edit/main/docs/:path`
- `specs/**` symlink → `...edit/main/specs/:path` (not `...edit/main/docs/specs/:path`)

**Suggestion:** Add to TASK-900 acceptance:
```
- [ ] `editLink.pattern` in config.ts is a function that routes:
  - docs/guide/* → github.com/arc-framework/arc-platform/edit/main/docs/:path
  - specs/* → github.com/arc-framework/arc-platform/edit/main/specs/:path
```

---

## Summary Table

| Category | Count | Issues |
|----------|-------|--------|
| **Blockers** | 5 | Task graph incomplete; Phase 2 permissions ambiguous; service count mismatch; US-6 scope conflict; gh workflow run input format unclear |
| **Warnings** | 3 | Old docs/specs cleanup not explicit; service count 14 vs 15; Principle II compliance mislabeled |
| **Observations** | 5 | Minor clarity improvements (help text, workflow validation, symlink preservation, port clarity, editLink pattern) |

---

## Recommended Actions Before Implementation

1. **Resolve BLOCKER-1:** Update task dependency graph (mermaid).
2. **Resolve BLOCKER-2:** Add explicit `permissions.actions: write` to TASK-100 and clarify risk mitigation.
3. **Resolve BLOCKER-3:** Create service-to-workflow mapping table and update success criteria for Phase 2.
4. **Resolve BLOCKER-4:** Decide whether US-6 moves to Phase 2 or becomes an architecture stub (without live service requirement).
5. **Resolve BLOCKER-5:** Clarify gh workflow run syntax with `-f` input flags in TASK-101 and plan.md.
6. **Address WARNING-1:** Add explicit cleanup verification to TASK-001.
7. **Address WARNING-2:** Update service count language in US-5 and TASK-021 to match SERVICE.MD reality (14 active + 8 planned).
8. **Address WARNING-3:** Correct Constitution Principle II status in plan.md to N/A (docs are orthogonal to platform-in-a-box).

---

## Recommendation

**PAUSE TO FIX BLOCKERS** before implementation begins.

The spec and plan are well-intentioned and comprehensive, but the 5 blockers create ambiguity in task sequencing, platform capabilities, and release workflow mechanics. Once these are clarified, implementation can proceed with confidence in parallel batches.

---

**Analysis Date:** 2026-03-10  
**Analyst Role:** Pre-implementation auditor (read-only)
