# Feature: Platform Control Plane Services Setup

> **Spec**: 006-platform-control
> **Author**: arc-framework
> **Date**: 2026-02-28
> **Status**: Draft

## Target Modules

| Module | Path | Impact |
|--------|------|--------|
| Services | `services/gateway/` | New — Traefik v3 (Heimdall), ports 80/8090 |
| Services | `services/secrets/` | New — OpenBao (Nick Fury), port 8200 |
| Services | `services/flags/` | New — Unleash (Mystique), port 4242 |
| Services | `services/profiles.yaml` | Update — heimdall → `think`; nick-fury + mystique → `reason` |
| CI/CD | `.github/workflows/` | New — control-images.yml + control-release.yml |
| Makefile | `Makefile`, `*.mk` | New — heimdall.mk, nick-fury.mk, mystique.mk, control.mk |

## Overview

Provision Traefik v3 (Heimdall), OpenBao (Nick Fury), and Unleash (Mystique) as the platform control plane. Heimdall is the HTTP ingress gateway with Docker label-based routing; Nick Fury provides secrets management in auto-unsealed dev mode; Mystique manages feature flags with Postgres (Oracle) and Redis (Sonic) as its backend. All three follow the canonical thin-wrapper pattern from 003-messaging-setup and 005-data-layer: Dockerfile with OCI labels, `service.yaml`, `docker-compose.yml`, `.mk` include, and CI/release workflows.

## Architecture

```mermaid
graph TD
    subgraph arc_platform_net
        heimdall["arc-heimdall\n(Traefik v3)\n:80 HTTP · :8090 dashboard"]
        fury["arc-nick-fury\n(OpenBao)\n:8200 API + UI"]
        mystique["arc-mystique\n(Unleash)\n:4242 UI + REST"]
        oracle["arc-oracle\n(Postgres 17)\n:5432"]
        sonic["arc-sonic\n(Redis)\n:6379"]
    end

    internet["External Traffic"] -->|HTTP :80| heimdall
    heimdall -->|label-based routing| services["Platform Services"]
    apps["Client Apps"] -->|secrets API| fury
    apps -->|feature flag eval| mystique
    mystique -->|feature flag state| oracle
    mystique -->|session cache| sonic
    dockersock["/var/run/docker.sock (ro)"] -.->|provider.docker| heimdall
```

### Service Roles

| Codename | Image | Port(s) | Role |
|----------|-------|---------|------|
| Heimdall | `traefik:v3` | 80 · 8090 | HTTP ingress; Docker label routing; no TLS in dev |
| Nick Fury | `openbao/openbao` | 8200 | Secrets API; dev mode auto-unsealed, in-memory |
| Mystique | `unleashorg/unleash-server` | 4242 | Feature flags; Postgres state + Redis cache |

### Directory Layout

```
services/
├── gateway/            ← Heimdall (Traefik v3)
│   ├── Dockerfile
│   ├── service.yaml
│   ├── docker-compose.yml
│   └── heimdall.mk
├── secrets/            ← Nick Fury (OpenBao)
│   ├── Dockerfile
│   ├── service.yaml
│   ├── docker-compose.yml
│   └── nick-fury.mk
└── flags/              ← Mystique (Unleash)
    ├── Dockerfile
    ├── service.yaml
    ├── docker-compose.yml
    └── mystique.mk
```

## User Scenarios & Testing

### P1 — Must Have

**US-1**: As a platform developer, I want to start all three control plane services with a single make command so the control plane is ready immediately.
- **Given**: Docker is running and `arc_platform_net` exists
- **When**: `make control-up` is executed
- **Then**: Heimdall, Nick Fury, and Mystique start; all Docker health checks pass
- **Test**: `make control-health` exits 0

**US-2**: As a platform developer, I want Heimdall to auto-discover running services via Docker labels so I can route HTTP traffic without editing config files.
- **Given**: Another service runs with `traefik.enable=true` label on `arc_platform_net`
- **When**: Heimdall is running
- **Then**: Route is available via Heimdall on port 80; dashboard at `:8090` shows the route
- **Test**: `curl -s http://localhost:8090/api/http/routers` lists the route

**US-3**: As a platform developer, I want Nick Fury running in dev mode so I can read/write secrets without unsealing.
- **Given**: `make nick-fury-up` has succeeded
- **When**: `curl -H "X-Vault-Token: arc-dev-token" http://localhost:8200/v1/sys/health`
- **Then**: HTTP 200; `"initialized": true, "sealed": false`
- **Test**: `make nick-fury-health` exits 0

**US-4**: As a platform developer, I want Mystique to start and serve the feature flag UI on `:4242` backed by Oracle and Sonic.
- **Given**: `arc-oracle` and `arc-sonic` are healthy; `make mystique-up` called
- **When**: `curl http://localhost:4242/health`
- **Then**: HTTP 200; Unleash UI accessible at `http://localhost:4242`
- **Test**: `make mystique-health` exits 0

### P2 — Should Have

**US-5**: As a CI consumer, I want Docker images for all three control services built and pushed on main merges.
- **Given**: A commit touches `services/gateway/**`, `services/secrets/**`, or `services/flags/**`
- **When**: `control-images.yml` workflow runs
- **Then**: `arc-heimdall`, `arc-nick-fury`, `arc-mystique` updated on GHCR with `sha-*` tag
- **Test**: GHCR package shows `sha-*` tag after CI

**US-6**: As a release engineer, I want versioned images via `control/vX.Y.Z` tag so control plane releases are atomic.
- **Test**: `git tag control/v0.1.0 && git push --tags` triggers `control-release.yml`; multi-platform images published

**US-7**: As a platform developer, I want each service to have `service.yaml` for declarative CLI discovery.
- **Test**: All three `service.yaml` files contain name, codename, image, ports, health, depends_on

### P3 — Nice to Have

**US-8**: As a developer, I want `make control-logs` to tail all three services simultaneously.
- **Test**: `make control-logs` fans out with `[heimdall]`, `[nick-fury]`, `[mystique]` prefixes

## Requirements

### Functional

- [ ] FR-1: Create `services/gateway/` with Traefik v3 Dockerfile (`traefik:v3`), `service.yaml`, `docker-compose.yml`, `heimdall.mk`
- [ ] FR-2: Create `services/secrets/` with OpenBao Dockerfile (`openbao/openbao`), `service.yaml`, `docker-compose.yml`, `nick-fury.mk`
- [ ] FR-3: Create `services/flags/` with Unleash Dockerfile (`unleashorg/unleash-server`), `service.yaml`, `docker-compose.yml`, `mystique.mk`
- [ ] FR-4: Heimdall must bind port 80 (HTTP) and 8090 (dashboard); configured via CLI args only (`--api.dashboard=true --providers.docker=true`); Docker socket mounted read-only; no TLS in dev
- [ ] FR-5: Nick Fury must run in OpenBao dev mode (`-dev` flag); root token set via `VAULT_DEV_ROOT_TOKEN_ID=arc-dev-token`; no persistent volume (stateless in dev)
- [ ] FR-6: Mystique must connect to Oracle via `DATABASE_URL=postgresql://arc:arc@arc-oracle:5432/unleash` and to Sonic via `REDIS_HOST=arc-sonic REDIS_PORT=6379`; DB migrations run automatically on startup
- [ ] FR-7: Update `services/profiles.yaml` — add `heimdall` to `think`; add `nick-fury` + `mystique` to `reason`
- [ ] FR-8: Create `control-images.yml` CI — path-filtered per service dir, builds all three, `linux/amd64` only in CI
- [ ] FR-9: Create `control-release.yml` — tag format `control/vX.Y.Z`, multi-platform (`linux/amd64,linux/arm64`), creates GitHub release
- [ ] FR-10: Create `services/control.mk` with `control-up`, `control-down`, `control-health`, `control-logs`
- [ ] FR-11: Include `heimdall.mk`, `nick-fury.mk`, `mystique.mk`, `control.mk` in root Makefile; add all three to `publish-all`

### Non-Functional

- [ ] NFR-1: Docker socket mounted read-only (`/var/run/docker.sock:/var/run/docker.sock:ro`) — Heimdall only
- [ ] NFR-2: Nick Fury is explicitly stateless in dev (no volume); documented in `nick-fury-help` output
- [ ] NFR-3: All ports bind to `127.0.0.1` only — no `0.0.0.0` exposure
- [ ] NFR-4: Verify non-root user for each upstream image; add `USER` + `RUN chown` in Dockerfile if root by default
- [ ] NFR-5: All Dockerfiles include OCI (`org.opencontainers.*`) and `arc.service.*` labels
- [ ] NFR-6: Mystique `service.yaml` `depends_on` references `oracle` and `sonic`
- [ ] NFR-7: CI build completes in under 3 minutes (amd64 only; no QEMU)

### Key Entities

| Entity | Module | Description |
|--------|--------|-------------|
| `arc-heimdall` | `services/gateway/` | Traefik v3; HTTP gateway, Docker label routing, dashboard at :8090 |
| `arc-nick-fury` | `services/secrets/` | OpenBao; dev-mode secrets API, auto-unsealed, token `arc-dev-token` |
| `arc-mystique` | `services/flags/` | Unleash; feature flags backed by Oracle (Postgres) + Sonic (Redis) |
| `heimdall.mk` | `services/gateway/` | Make targets: heimdall-up/down/health/logs/build/push/publish/tag/clean/nuke |
| `nick-fury.mk` | `services/secrets/` | Make targets: nick-fury-up/down/health/logs/build/push/publish/tag/clean/nuke |
| `mystique.mk` | `services/flags/` | Make targets: mystique-up/down/health/logs/build/push/publish/tag/clean/nuke |

## Port Reference

| Service | Container Port | Host Binding | Purpose |
|---------|---------------|--------------|---------|
| Heimdall | 80 | `127.0.0.1:80` | HTTP entrypoint — routes to platform services |
| Heimdall | 8090 | `127.0.0.1:8090` | Traefik dashboard (avoids :8081 Cortex, :8082 Pulsar) |
| Nick Fury | 8200 | `127.0.0.1:8200` | OpenBao API + Web UI |
| Mystique | 4242 | `127.0.0.1:4242` | Unleash REST API + Web UI |

## Network Strategy

All three services join `arc_platform_net` only. Heimdall additionally mounts the Docker socket (bind mount, not a network) for service discovery.

```mermaid
graph LR
    subgraph arc_platform_net [arc_platform_net — external, shared]
        heimdall[arc-heimdall]
        fury[arc-nick-fury]
        mystique[arc-mystique]
        oracle[arc-oracle]
        sonic[arc-sonic]
    end
    dockersock["/var/run/docker.sock"] -.->|read-only bind| heimdall
```

**Rules:**
- `arc_platform_net` declared `external: true` in all three compose files
- Mystique must be on the same network as `arc-oracle` and `arc-sonic`
- Container hostnames are DNS-resolvable across the network (used by Mystique's `DATABASE_URL`)

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `make mystique-up` before Oracle ready | Unleash retries DB connection; health fails until Oracle is healthy |
| `make mystique-up` before Sonic ready | Unleash starts in Postgres-only mode; logs Redis warning; feature flags still work |
| Nick Fury restarts | All secrets lost (in-memory dev mode); clients must re-fetch — expected, documented |
| Heimdall dashboard port :8090 conflicts | Startup fails; check `make dev-status` for port occupants |
| Service starts without `traefik.enable=true` | Not routed by Heimdall — opt-in model by design |
| `make control-up` before `arc_platform_net` exists | Docker compose fails at network lookup; run `make dev-networks` or `docker network create arc_platform_net` |
| Mystique DB migration fails on startup | Container exits non-zero; check `make mystique-logs` — usually a DB connection issue |
| Unleash default admin credentials | Unleash auto-creates admin user on first boot; credentials printed in logs |

## Success Criteria

- [ ] SC-1: `make control-up && make control-health` exits 0; all three containers healthy
- [ ] SC-2: Traefik dashboard accessible at `http://localhost:8090`
- [ ] SC-3: `curl -H "X-Vault-Token: arc-dev-token" http://localhost:8200/v1/sys/health` returns HTTP 200
- [ ] SC-4: Unleash UI accessible at `http://localhost:4242`; `/health` returns 200
- [ ] SC-5: `control-images.yml` CI completes in under 3 minutes (amd64 only)
- [ ] SC-6: `git tag control/v0.1.0` triggers `control-release.yml`; multi-platform images on GHCR
- [ ] SC-7: All Dockerfiles pass `trivy image` scan with zero CRITICAL CVEs
- [ ] SC-8: `services/profiles.yaml` `think` profile includes `heimdall`; `reason` profile includes `nick-fury` and `mystique`

## Docs & Links Update

- [ ] Update `services/profiles.yaml` — heimdall → `think`; nick-fury + mystique → `reason`
- [ ] Update `CLAUDE.md` monorepo layout to reference `gateway/`, `secrets/`, `flags/` directories
- [ ] Update `CLAUDE.md` Service Codenames table — Nick Fury: Infisical → OpenBao
- [ ] Update `.specify/config.yaml` `secrets` entry — change tech from `infisical` to `openbao`
- [ ] Verify `services/flags/service.yaml` `depends_on` lists `oracle` and `sonic`

## Constitution Compliance

| Principle | Applies | Compliant | Notes |
|-----------|---------|-----------|-------|
| I. Zero-Dep CLI | [ ] | n/a | Services only — no CLI changes |
| II. Platform-in-a-Box | [x] | [x] | `make control-up` boots all three; heimdall joins `think` profile |
| III. Modular Services | [x] | [x] | Each self-contained in own directory; flat under `services/` |
| IV. Two-Brain | [x] | [x] | Config-only upstream images — no language concern |
| V. Polyglot Standards | [x] | [x] | Follows 003/005 patterns: Dockerfile, compose, .mk, CI |
| VI. Local-First | [ ] | n/a | CLI-only principle |
| VII. Observability | [x] | [x] | Traefik dashboard + metrics; OpenBao `/v1/sys/health`; Unleash `/health` |
| VIII. Security | [x] | [x] | Non-root containers; 127.0.0.1-only; Docker socket ro; no secrets in git |
| IX. Declarative | [ ] | n/a | CLI-only principle |
| X. Stateful Ops | [ ] | n/a | CLI-only principle |
| XI. Resilience | [x] | [x] | Health checks with start_periods; Mystique compose `depends_on` oracle + sonic |
| XII. Interactive | [ ] | n/a | CLI-only principle |
