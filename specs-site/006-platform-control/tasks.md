---
url: /arc-platform/specs-site/006-platform-control/tasks.md
---
# Tasks: Platform Control Plane Services Setup

> **Spec**: 006-platform-control
> **Date**: 2026-02-28

## Task Format

```
[TASK-NNN] [P?] [MODULE] [PRIORITY] Description
  Dependencies: [TASK-XXX] or none
  Module: services/{role}
  Acceptance: Testable criteria
  Status: [ ] pending | [~] in-progress | [x] done
```

* `[P]` = Safe for parallel agent execution
* Priority: P1 (must), P2 (should), P3 (nice)

## Dependency Graph

```mermaid
graph TD
    T001["TASK-001\nprofiles.yaml"] --> T011
    T001 --> T012
    T001 --> T013

    T011["TASK-011 [P]\nservices/gateway/\nHeimdall"] --> T021
    T012["TASK-012 [P]\nservices/secrets/\nNick Fury"] --> T022
    T013["TASK-013 [P]\nservices/flags/\nMystique"] --> T023

    T021["TASK-021 [P]\nheimdall.mk"] --> T024
    T022["TASK-022 [P]\nnick-fury.mk"] --> T024
    T023["TASK-023 [P]\nmystique.mk"] --> T024

    T024["TASK-024\ncontrol.mk +\nMakefile includes"] --> T031
    T024 --> T032

    T031["TASK-031 [P]\ncontrol-images.yml"] --> T041
    T032["TASK-032 [P]\ncontrol-release.yml"] --> T041

    T041["TASK-041\nE2E verification"] --> T900
    T041 --> T999

    T900["TASK-900\nDocs & links"] --> T999
    T999["TASK-999\nReviewer"]
```

## Quality Requirements

| Module | Coverage | Lint | Notes |
|--------|----------|------|-------|
| Config/YAML | n/a | `docker compose config` (no syntax errors) | |
| Makefile | n/a | `make -n {target}` dry-run passes | |
| CI/CD YAML | n/a | GitHub Actions YAML schema valid | |

***

## Phase 1: Setup

* \[x] \[TASK-001] \[SERVICES] \[P1] Update profiles.yaml — heimdall → `think`; nick-fury + mystique → `reason`
  * Dependencies: none
  * Module: `services/profiles.yaml`
  * Acceptance:
    * Python YAML validation confirms structure (not just text presence):
      ```
      python3 -c "
      import yaml
      p = yaml.safe_load(open('services/profiles.yaml'))
      assert 'heimdall' in p['think']['services'], 'heimdall missing from think'
      assert 'nick-fury' in p['reason']['services'], 'nick-fury missing from reason'
      assert 'mystique' in p['reason']['services'], 'mystique missing from reason'
      assert p['ultra-instinct']['services'] == '*', 'ultra-instinct changed'
      print('profiles.yaml OK')
      "
      ```
    * Existing services in `think` preserved: flash, sonic, strange, friday-collector, cortex, oracle, cerebro
    * Existing services in `reason` preserved: cortex, flash, strange, sonic, otel, tardis

***

## Phase 2: Foundational — Service Directories (parallel)

All three tasks are fully independent. Each creates: `Dockerfile`, `service.yaml`, `docker-compose.yml`. Make targets handled in Phase 3.

* \[x] \[TASK-011] \[P] \[SERVICES] \[P1] Create `services/gateway/` — Heimdall (Traefik v3)
  * Dependencies: TASK-001
  * Module: `services/gateway/`
  * Acceptance:
    * `Dockerfile`: `FROM traefik:v3`; OCI labels (`org.opencontainers.image.title`, `description`, `source`); `arc.service.name=arc-gateway`, `arc.service.codename=heimdall`, `arc.service.tech=traefik`; `USER 1000` (non-root via non-privileged internal ports)
    * `service.yaml`: name `arc-gateway`, codename `heimdall`, image `ghcr.io/arc-framework/arc-gateway:latest`, tech `traefik`, upstream `traefik:v3`, ports `[80, 8090]`, health `http://localhost:8090/ping`, depends\_on `[]`
    * `docker-compose.yml`: service `arc-gateway`; command includes `--api.insecure=true`, `--api.dashboard=true`, `--ping=true`, `--providers.docker=true`, `--providers.docker.network=arc_platform_net`, `--providers.docker.exposedbydefault=false`, `--entrypoints.web.address=:8080`, `--entrypoints.dashboard.address=:8090`; ports `127.0.0.1:80:8080` and `127.0.0.1:8090:8090`; volumes `/var/run/docker.sock:/var/run/docker.sock:ro`; `user: "1000:1000"`; healthcheck `traefik healthcheck --ping` interval 5s, timeout 3s, retries 5, start\_period 5s; no persistent volume; network `arc_platform_net` (external); `restart: unless-stopped`
    * `docker compose config` passes without errors
    * `docker build -f services/gateway/Dockerfile services/gateway/` succeeds
    * Note: if `USER 1000` causes Traefik to fail at runtime, remove `USER 1000` and document root deviation in Dockerfile comment (same Pulsar pattern from 003)

* \[x] \[TASK-012] \[P] \[SERVICES] \[P1] Create `services/secrets/` — Nick Fury (OpenBao)
  * Dependencies: TASK-001
  * Module: `services/secrets/`
  * Acceptance:
    * `Dockerfile`: `FROM openbao/openbao`; OCI labels; `arc.service.name=arc-vault`, `arc.service.codename=nick-fury`, `arc.service.tech=openbao`; **Dockerfile MUST contain** this exact comment (or equivalent): `# openbao/openbao runs as root by default. Nick Fury uses -dev mode: in-memory, auto-unsealed, known root token. Root is acceptable for this DEVELOPMENT-ONLY service. For production: Raft-backed storage + TLS + non-root user.`
    * `service.yaml`: name `arc-vault`, codename `nick-fury`, image `ghcr.io/arc-framework/arc-vault:latest`, tech `openbao`, upstream `openbao/openbao`, ports `[8200]`, health `http://localhost:8200/v1/sys/health`, depends\_on `[]`
    * `docker-compose.yml`: service `arc-vault`; command `server -dev`; env `VAULT_DEV_ROOT_TOKEN_ID=arc-dev-token`, `VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200`; port `127.0.0.1:8200:8200`; no volume (stateless dev); healthcheck: attempt `wget -qO- http://localhost:8200/v1/sys/health || exit 1`; if `wget` absent use bash `/dev/tcp` pattern (same as arc-vector-db); interval 5s, timeout 3s, retries 5, start\_period 5s; network `arc_platform_net` (external); `restart: unless-stopped`
    * `docker compose config` passes without errors
    * `docker build -f services/secrets/Dockerfile services/secrets/` succeeds
    * No volume declared (Nick Fury is stateless in dev — data lost on restart is expected and documented)

* \[x] \[TASK-013] \[P] \[SERVICES] \[P1] Create `services/flags/` — Mystique (Unleash)
  * Dependencies: TASK-001
  * Module: `services/flags/`, `services/persistence/initdb/`
  * Acceptance:
    * `Dockerfile`: `FROM unleashorg/unleash-server`; OCI labels; `arc.service.name=arc-flags`, `arc.service.codename=mystique`, `arc.service.tech=unleash`; attempt `USER 1000` (non-root); if Unleash fails to start, remove and add comment: "# NOTE: unleashorg/unleash-server requires root — upstream constraint"
    * `service.yaml`: name `arc-flags`, codename `mystique`, image `ghcr.io/arc-framework/arc-flags:latest`, tech `unleash`, upstream `unleashorg/unleash-server`, ports `[4242]`, health `http://localhost:4242/health`, depends\_on `[oracle, sonic]`
    * `docker-compose.yml`: service `arc-flags`; env `DATABASE_URL=postgresql://arc:arc@arc-sql-db:5432/unleash`, `REDIS_HOST=arc-cache`, `REDIS_PORT=6379`; port `127.0.0.1:4242:4242`; no persistent volume; healthcheck `wget -qO- http://localhost:4242/health || exit 1` interval 10s, timeout 5s, retries 10, **start\_period 30s** (Unleash runs DB migrations on first boot); network `arc_platform_net` (external); `restart: unless-stopped`
    * **Oracle init SQL** (cross-service, justified): create `services/persistence/initdb/002_create_unleash_db.sql` containing `CREATE DATABASE unleash;`
      * Justification: Oracle (the database service) is the rightful owner of "what databases exist". Mystique declares the need; Oracle satisfies it via initdb. This follows the same pattern as `001_schema_migrations.sql` (created in 005 for Cortex's needs). Not a Principle III violation — initdb is Oracle's extension point for dependent services.
      * This file runs on Oracle's first boot only (Postgres skips initdb if data dir exists). To force re-creation: `make oracle-nuke && make oracle-up`
    * `docker compose config` passes without errors
    * `docker build -f services/flags/Dockerfile services/flags/` succeeds

***

## Phase 3: Make Targets

### Batch A — parallel (each .mk is independent)

* \[x] \[TASK-021] \[P] \[SERVICES] \[P1] Create `services/gateway/heimdall.mk`
  * Dependencies: TASK-011
  * Module: `services/gateway/heimdall.mk`
  * Acceptance:
    * Targets present: `heimdall-help`, `heimdall-build`, `heimdall-build-fresh`, `heimdall-up`, `heimdall-down`, `heimdall-health`, `heimdall-logs`, `heimdall-push`, `heimdall-publish`, `heimdall-tag`, `heimdall-clean`, `heimdall-nuke`
    * `heimdall-health`: probes `curl -sf http://localhost:8090/ping`; exits 0 if healthy, 1 if not
    * `heimdall-clean` / `heimdall-nuke`: require typed confirmation (`yes` / `nuke`) before destructive action
    * `heimdall-publish`: pushes image then prints `https://github.com/orgs/$(ORG)/packages/container/arc-gateway/settings`
    * `make heimdall-help` lists all targets with descriptions; output includes note: "Port 80 binding requires Docker privilege. If startup fails with 'permission denied', change host port in a docker-compose.override.yml"
    * All targets use `COLOR_INFO`, `COLOR_OK`, `COLOR_ERR` from root Makefile
    * `make -n heimdall-up` dry-run passes

* \[x] \[TASK-022] \[P] \[SERVICES] \[P1] Create `services/secrets/nick-fury.mk`
  * Dependencies: TASK-012
  * Module: `services/secrets/nick-fury.mk`
  * Acceptance:
    * Targets present: `nick-fury-help`, `nick-fury-build`, `nick-fury-build-fresh`, `nick-fury-up`, `nick-fury-down`, `nick-fury-health`, `nick-fury-logs`, `nick-fury-push`, `nick-fury-publish`, `nick-fury-tag`, `nick-fury-clean`, `nick-fury-nuke`
    * `nick-fury-health`: probes `curl -sf http://localhost:8200/v1/sys/health`; exits 0 if healthy, 1 if not
    * `nick-fury-nuke`: warns "All secrets will be lost (stateless dev service)" before destructive action; requires typed confirmation
    * `nick-fury-help` output mentions "Dev mode only — all secrets lost on restart"
    * `make nick-fury-help` lists all targets
    * `make -n nick-fury-up` dry-run passes

* \[x] \[TASK-023] \[P] \[SERVICES] \[P1] Create `services/flags/mystique.mk`
  * Dependencies: TASK-013
  * Module: `services/flags/mystique.mk`
  * Acceptance:
    * Targets present: `mystique-help`, `mystique-build`, `mystique-build-fresh`, `mystique-up`, `mystique-down`, `mystique-health`, `mystique-logs`, `mystique-push`, `mystique-publish`, `mystique-tag`, `mystique-clean`, `mystique-nuke`
    * `mystique-health`: probes `curl -sf http://localhost:4242/health`; exits 0 if healthy, 1 if not
    * `mystique-help` output includes note: "Requires arc-sql-db and arc-cache to be running"
    * `mystique-clean` / `mystique-nuke`: require typed confirmation before destructive action
    * `make mystique-help` lists all targets
    * `make -n mystique-up` dry-run passes

### Batch B — sequential (depends on all Batch A)

* \[x] \[TASK-024] \[SERVICES] \[P1] Create `services/control.mk` + update root `Makefile`
  * Dependencies: TASK-021, TASK-022, TASK-023
  * Module: `services/control.mk`, `Makefile`
  * Acceptance:
    * `services/control.mk` targets: `control-help`, `control-up`, `control-down`, `control-health`, `control-logs`
    * `control-up`: calls `docker network create arc_platform_net 2>/dev/null || true`, then `heimdall-up`, `nick-fury-up`, `mystique-up` sequentially
    * `control-down`: calls `mystique-down`, `nick-fury-down`, `heimdall-down` (reverse order)
    * `control-health`: calls all three health targets; exits non-zero if any fails
    * `control-logs`: fans out logs from all three containers with service name prefixes
    * Root `Makefile` additions:
      * `include services/gateway/heimdall.mk`
      * `include services/secrets/nick-fury.mk`
      * `include services/flags/mystique.mk`
      * `include services/control.mk`
    * `publish-all` target updated to include `heimdall-build heimdall-publish`, `nick-fury-build nick-fury-publish`, `mystique-build mystique-publish`
    * `make control-help` lists control-\* targets
    * `make -n control-up` dry-run shows correct chain

***

## Phase 4: CI/CD (parallel)

Both workflows are independent and can be implemented concurrently.

* \[x] \[TASK-031] \[P] \[CI] \[P1] Create `.github/workflows/control-images.yml`
  * Dependencies: TASK-024
  * Module: `.github/workflows/control-images.yml`
  * Acceptance:
    * Mirrors `data-images.yml` structure exactly
    * `on.push.paths`: `services/gateway/**`, `services/secrets/**`, `services/flags/**`, `.github/workflows/control-images.yml`
    * `on.pull_request.paths`: same service paths
    * `on.workflow_dispatch` with `mode` input (`ci` / `release`)
    * `changes` job uses `dorny/paths-filter@v3` with filters `heimdall`, `nick-fury`, `mystique`
    * `build-heimdall`, `build-nick-fury`, `build-mystique` jobs: parallel, each uses `_reusable-build.yml`
      * `platforms: linux/amd64`
      * `service-path: services/gateway` / `services/secrets` / `services/flags`
    * `security-heimdall`, `security-nick-fury`, `security-mystique` jobs: run after respective builds; `block-on-failure: false` in CI
    * YAML parses without errors: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/control-images.yml'))"` exits 0

* \[x] \[TASK-032] \[P] \[CI] \[P1] Create `.github/workflows/control-release.yml`
  * Dependencies: TASK-024
  * Module: `.github/workflows/control-release.yml`
  * Acceptance:
    * Mirrors `data-release.yml` structure exactly
    * `on.push.tags`: `control/v*`
    * `prepare` job: derives `image-tag` (`control/v0.1.0` → `control-v0.1.0`), `version`, `prerelease` outputs
    * `build-heimdall`, `build-nick-fury`, `build-mystique`: parallel after `prepare`; `platforms: linux/amd64,linux/arm64`; `push-image: true`, `latest-tag: true`, `image-tag: ${{ needs.prepare.outputs.image-tag }}`
    * `security-*` jobs: `block-on-failure: true`; `create-issues: true` (CRITICAL CVEs block release)
    * `release` job: image table (arc-gateway, arc-vault, arc-flags); creates GitHub release via `softprops/action-gh-release@v2`
    * Release notes include `make control-up` / `make control-health` quickstart
    * YAML parses without errors

***

## Phase 5: Integration

* \[x] \[TASK-041] \[SERVICES] \[P1] End-to-end verification — control plane up + health
  * Dependencies: TASK-031, TASK-032
  * Module: `services/gateway/`, `services/secrets/`, `services/flags/`
  * Pre-condition: `arc-sql-db` and `arc-cache` must be running (`make oracle-up sonic-up` first)
  * Acceptance:
    * `docker network create arc_platform_net 2>/dev/null || true` runs without error
    * `make control-up` exits 0; `docker compose ps` shows arc-gateway, arc-vault, arc-flags all in `healthy` state
    * `make control-health` exits 0 (all three health probes pass)
    * `make control-down` exits 0; all three containers stop; no orphaned containers
    * Independent health checks pass: `make heimdall-health`, `make nick-fury-health`, `make mystique-health`
    * `curl -sf http://localhost:8090/ping` returns `OK`
    * Traefik dashboard accessible: `curl -sf http://localhost:8090/dashboard/` returns HTTP 200
    * `curl -H "X-Vault-Token: arc-dev-token" http://localhost:8200/v1/sys/health` returns HTTP 200 with `"sealed":false`
    * `curl http://localhost:4242/health` returns HTTP 200
    * All ports bound to `127.0.0.1`: `docker compose ps` confirms
    * No persistent volumes for Heimdall or Nick Fury: `docker volume ls | grep arc` shows no `arc-gateway-*` or `arc-vault-*`
    * Heimdall uid verified: `docker inspect arc-gateway --format '{{.Config.User}}'` returns `1000:1000` or `1000` (or root documented)
    * `services/persistence/initdb/002_create_unleash_db.sql` exists; Mystique connects to Unleash DB without error

***

## Phase 6: Polish

* \[x] \[TASK-900] \[P] \[DOCS] \[P1] Docs & links update
  * Dependencies: TASK-041
  * Module: `services/profiles.yaml`, `CLAUDE.md`, `.specify/config.yaml`
  * Acceptance:
    * `services/profiles.yaml` `think` profile includes `heimdall` (already done in TASK-001 — verify final state)
    * `services/profiles.yaml` `reason` profile includes `nick-fury` and `mystique`
    * `CLAUDE.md` monorepo layout section references `gateway/`, `secrets/`, `flags/` directories
    * `CLAUDE.md` Service Codenames table updated: Nick Fury row shows `OpenBao` (not `Infisical`)
    * `.specify/config.yaml` `secrets` service entry: `tech` changed from `infisical` to `openbao`
    * No broken internal references in modified files

* \[x] \[TASK-999] \[REVIEW] \[P1] Reviewer agent verification
  * Dependencies: ALL
  * Module: all affected modules
  * Acceptance (full checklist — reviewer runs all items without needing to open plan.md):
    * All tasks TASK-001 through TASK-900 marked `[x]` complete
    * `make control-up` exits 0 (pre-condition: oracle + sonic running via `make oracle-up sonic-up`)
    * `docker compose ps` shows arc-gateway, arc-vault, arc-flags all in `healthy` state
    * `make control-health` exits 0
    * `make control-down` exits 0; no orphaned containers
    * `make heimdall-up && make heimdall-health` works independently
    * `make nick-fury-up && make nick-fury-health` works independently
    * `make mystique-up && make mystique-health` works independently (requires oracle + sonic)
    * `curl http://localhost:8090/ping` returns `OK`
    * `curl http://localhost:8090/dashboard/` returns HTTP 200
    * `curl -H "X-Vault-Token: arc-dev-token" http://localhost:8200/v1/sys/health` returns HTTP 200 with `"sealed":false`
    * `curl http://localhost:4242/health` returns HTTP 200
    * `docker inspect arc-gateway --format '{{.Config.User}}'` confirms uid 1000 (or root deviation documented)
    * `docker inspect arc-flags --format '{{.Config.User}}'` confirms non-root or deviation documented
    * Nick Fury Dockerfile contains comment explaining root deviation + dev-only scope
    * All ports bind `127.0.0.1`: verify with `docker compose ps`
    * No persistent volumes for Heimdall or Nick Fury: `docker volume ls | grep arc` shows no `arc-gateway-*` or `arc-vault-*`
    * `services/profiles.yaml` `think` includes `heimdall`; `reason` includes `nick-fury` + `mystique`
    * `Makefile` includes `heimdall.mk`, `nick-fury.mk`, `mystique.mk`, `control.mk`
    * `publish-all` includes `heimdall-build heimdall-publish`, `nick-fury-build nick-fury-publish`, `mystique-build mystique-publish`
    * `control-images.yml` path filters: `services/gateway/**`, `services/secrets/**`, `services/flags/**`
    * `control-release.yml` tag format `control/v*`; platforms `linux/amd64,linux/arm64`
    * All three Dockerfiles have OCI (`org.opencontainers.*`) + `arc.service.*` labels
    * No plaintext credentials in any compose file (env values are dev defaults, not production secrets)
    * `CLAUDE.md` Service Codenames table: Nick Fury row shows `OpenBao` (not `Infisical`)
    * `.specify/config.yaml` `secrets` service entry: `tech: openbao`
    * `services/persistence/initdb/002_create_unleash_db.sql` exists
    * Constitution compliance verified: II PASS, III PASS, IV PASS, V PASS, VII PASS, VIII PASS†, XI PASS
      * VIII†: Nick Fury root deviation justified (dev-only, documented)

***

## Progress Summary

| Phase | Total | Done | Parallel |
|-------|-------|------|----------|
| Setup | 1 | 1 | 0 |
| Foundational | 3 | 3 | 3 |
| Implementation (Make + CI) | 6 | 6 | 5 |
| Integration | 1 | 1 | 0 |
| Polish | 2 | 2 | 0 |
| **Total** | **13** | **13** | **8** |
