# Analysis Report: 014-decouple-service-codenames

> **Date**: 2026-03-05
> **Stage**: Pre-implementation
> **Result**: CLEARED — all blockers resolved

## Coverage Matrix

| Req | Plan Section | Task | Acceptance |
|-----|-------------|------|-----------|
| FR-1 | Track A1 | TASK-010 | ✓ |
| FR-2 | Track A2 | TASK-020 | ✓ |
| FR-3 | Track A3 | TASK-021 | ✓ |
| FR-4 | Track A3 | TASK-021 | ✓ |
| FR-5 | Track C | TASK-027 | ✓ |
| FR-6 | Track D | TASK-028 | ✓ |
| FR-7 | Track B1 | TASK-025 | ✓ |
| FR-8 | Track B2-B4 | TASK-026 | ✓ |
| FR-9 | Track A4 | TASK-022 | ✓ |
| FR-10 | Track E | TASK-023 | ✓ |
| FR-11 | Track E | TASK-024 | ✓ |
| FR-12 | Track F | TASK-029 | ✓ (includes profiles.yaml alias) |
| FR-13 | Track G | TASK-031 | ✓ |

## Gaps Resolved

| Gap | Fix Applied |
|-----|-------------|
| TASK-040 referenced non-existent TASK-030 | Replaced with TASK-029 + TASK-031 |
| SC-2 path pointed to old `src/sherlock/` | Updated to `src/reasoner/` |
| profiles.yaml `sql-db` alias not in TASK-029 scope | Added to module list + acceptance criteria |
| Stale migration-window mermaid diagram in spec | Removed |
| Stale FR-11 (migration window requirement) | Removed — no external consumers confirmed |
| Stale NFR-1 (zero-downtime NATS migration) | Removed — renaming directly |
| Stale SC-6 (old subject integration test) | Replaced with `sql-db` profile alias check |
| Stale edge case (old sherlock.* NATS) | Removed |
| Stale constitution note (XI Resilience → migration window) | Updated to reflect container rename atomicity |
| TASK-999 reviewer checklist referenced dropped features | Cleaned up |

## Risks (remaining)

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `ultra-instinct` profile uses `services: '*'` — picks up all services | Low | Confirms vector removal is safe; `'*'` will not include deleted directory |
| SDK pinned to `arc-sherlock` package name | Low | Documented out-of-scope; SDK must bump independently |
| Partial import rename missed in RAG sub-modules | Medium | SC-1 grep + mypy catches at TASK-040 |

## Parallel Opportunities

All tasks correctly marked `[P]`. No unparallelized opportunities identified.

TASK-001 (audit) has no dependencies and could run in parallel with Phase 2 start, but it is correctly placed as a gate — its output affects all subsequent task scope.

## Constitution Compliance

| Principle | Status | Evidence |
|-----------|--------|----------|
| II. Platform-in-a-Box | PASS | `arc run --profile think` zero env overrides verified by SC-4 + SC-13 |
| III. Modular Services | PASS | Rename is internal per service; no inter-service coupling introduced |
| IV. Two-Brain | PASS | Python tracks (A-E) and Go tracks (B, F) never cross |
| V. Polyglot Standards | PASS | ruff + mypy + golangci-lint required in TASK-040 |
| VII. Observability | PASS | OTEL service name updated to `arc-reasoner`; metric namespace updated |
| VIII. Security | PASS | Non-root user unchanged; no secrets involved |
| XI. Resilience | PASS | Container rename + profile alias update applied atomically across all consumers |
