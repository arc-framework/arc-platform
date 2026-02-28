# Implementation Plan: Platform Control Plane Services Setup

> **Spec**: 006-platform-control
> **Date**: 2026-02-28

## Summary

Add three control plane services — Traefik v3 (Heimdall), OpenBao (Nick Fury), Unleash (Mystique) — each following the same structural pattern as 003-messaging-setup and 005-data-layer: thin Dockerfile label wrapper, `service.yaml`, `docker-compose.yml`, dedicated `.mk` include, CI/release workflows. All three join `arc_platform_net`. Non-root handling requires per-service decisions: Heimdall uses internal port remapping (non-privileged :8080 proxy); Nick Fury documents root deviation (dev mode is inherently insecure by design); Mystique attempts `user: "1000:1000"` at runtime. Profiles updated so `think` includes heimdall; `reason` adds nick-fury + mystique.

## Target Modules

| Module | Language | Changes |
|--------|----------|---------|
| `services/gateway/` | Config/Dockerfile | New — Traefik v3 (Heimdall) |
| `services/secrets/` | Config/Dockerfile | New — OpenBao (Nick Fury) |
| `services/flags/` | Config/Dockerfile | New — Unleash (Mystique) |
| `services/profiles.yaml` | YAML | Add heimdall to `think`; nick-fury + mystique to `reason` |
| `.github/workflows/` | YAML | New — control-images.yml + control-release.yml |
| `Makefile` | Make | Include heimdall.mk, nick-fury.mk, mystique.mk, control.mk + publish-all |
| `services/control.mk` | Make | New — aggregate up/down/health/logs |

## Technical Context

| Aspect | Value |
|--------|-------|
| Language | Config-only (YAML, Dockerfile, Makefile) — no application code |
| Base Images | `traefik:v3`, `openbao/openbao`, `unleashorg/unleash-server` |
| Testing | `traefik healthcheck --ping`, `/v1/sys/health`, `curl /health` |
| Network | `arc_platform_net` (external bridge, pre-existing) |
| Volumes | None for Heimdall/Nick Fury (stateless in dev); none for Mystique (DB-backed) |
| CI Pattern | Mirror `data-images.yml` — amd64-only CI, dorny/paths-filter per service |
| Root handling | Heimdall: port remap to uid 1000; Nick Fury: root documented; Mystique: try uid 1000 |

## Architecture

### Service topology

```mermaid
graph TB
    subgraph Host
        subgraph arc_platform_net
            heimdall["arc-gateway\ntraefik:v3\n:8080 proxy (host→:80)\n:8090 dashboard"]
            fury["arc-vault\nopenbao/openbao\n:8200 API + UI"]
            mystique["arc-flags\nunleash-server\n:4242 UI + REST"]
            oracle["arc-sql-db\npostgres:17\n:5432"]
            sonic["arc-cache\nredis\n:6379"]
        end
        dockersock["/var/run/docker.sock (ro)"]
    end

    dockersock -.->|providers.docker| heimdall
    mystique -->|DATABASE_URL| oracle
    mystique -->|REDIS_HOST| sonic
    apps["Clients"] -->|HTTP :80| heimdall
    apps -->|secrets :8200| fury
    apps -->|flags :4242| mystique
```

### Heimdall port remapping (non-root strategy)

```mermaid
graph LR
    host80["Host :80"] -->|127.0.0.1:80:8080| proxy["Container :8080\nTraefik entrypoint.web"]
    host8090["Host :8090"] -->|127.0.0.1:8090:8090| dash["Container :8090\nTraefik API/dashboard\n--api.insecure=true"]
    docker["Docker socket (ro)"] -->|label discovery| proxy
```

Internal container ports are non-privileged (`≥1024`), so Traefik runs as `uid 1000` without any capabilities.

### File pattern (identical across all three)

```mermaid
graph LR
    A["Dockerfile\nFROM upstream\nOCI + arc labels\nnon-root where possible"] --> B["docker-compose.yml\n127.0.0.1 ports\narc_platform_net external\nenv / command flags"]
    B --> C["service.yaml\nname, codename, image\nports, health, depends_on"]
    C --> D["{service}.mk\nup · down · health · logs\nbuild · push · publish · tag\nclean · nuke · help"]
```

## Key Implementation Decisions

### 1. Heimdall — Non-root via internal port remapping

Traefik in default config binds to privileged port 80 (requires root). Solution: configure internal entrypoints on non-privileged ports; remap at the Docker host layer.

```dockerfile
# services/gateway/Dockerfile
FROM traefik:v3
LABEL org.opencontainers.image.title="ARC Heimdall — API Gateway"
LABEL org.opencontainers.image.description="Traefik v3 ingress gateway for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-gateway"
LABEL arc.service.codename="heimdall"
LABEL arc.service.tech="traefik"
# traefik:v3 runs as root by default. We configure internal ports ≥1024
# so the process runs as uid 1000 without CAP_NET_BIND_SERVICE.
USER 1000
```

```yaml
# services/gateway/docker-compose.yml
arc-gateway:
  command:
    - --api.insecure=true                          # dashboard on internal :8090
    - --api.dashboard=true
    - --ping=true                                  # /ping healthcheck endpoint
    - --providers.docker=true
    - --providers.docker.network=arc_platform_net
    - --providers.docker.exposedbydefault=false    # opt-in only via labels
    - --entrypoints.web.address=:8080              # non-privileged proxy port
    - --entrypoints.dashboard.address=:8090        # dashboard port
  ports:
    - "127.0.0.1:80:8080"     # host:80 → container proxy (non-privileged inside)
    - "127.0.0.1:8090:8090"   # dashboard
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  user: "1000:1000"
  healthcheck:
    test: ["CMD", "traefik", "healthcheck", "--ping"]
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 5s
```

**Key**: `--providers.docker.exposedbydefault=false` means services must opt-in via `traefik.enable=true` label. Prevents unintentional routing.

### 2. Nick Fury — Root deviation (documented, dev mode by design)

OpenBao in dev mode (`-dev` flag) is intentionally insecure: in-memory storage, known root token, auto-unsealed. Running as root is consistent with the dev-only posture of this service. Document in Dockerfile and help text.

```dockerfile
# services/secrets/Dockerfile
FROM openbao/openbao
LABEL arc.service.name="arc-vault"
LABEL arc.service.codename="nick-fury"
LABEL arc.service.tech="openbao"
# openbao/openbao runs as root by default.
# Nick Fury uses -dev mode (in-memory, auto-unsealed, known root token).
# This is a DEVELOPMENT-ONLY service. Root is acceptable for dev-mode OpenBao.
# For production: use Raft-backed storage with TLS + non-root user.
```

```yaml
# services/secrets/docker-compose.yml
arc-vault:
  command: server -dev
  environment:
    VAULT_DEV_ROOT_TOKEN_ID: arc-dev-token
    VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
  ports:
    - "127.0.0.1:8200:8200"
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:8200/v1/sys/health || exit 1"]
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 5s
```

If `wget` is absent in the openbao image, fall back to bash `/dev/tcp` (same pattern as Cerebro).

### 3. Mystique — Non-root attempt, document if fails

Unleash is a Node.js app. `user: "1000:1000"` in compose is the first attempt. If Unleash writes to privileged paths at startup, document the root deviation in compose comments (like Pulsar in 003).

```yaml
# services/flags/docker-compose.yml
arc-flags:
  user: "1000:1000"   # attempt non-root; remove + add comment if Unleash refuses to start
  environment:
    DATABASE_URL: postgresql://arc:arc@arc-sql-db:5432/unleash
    REDIS_HOST: arc-cache
    REDIS_PORT: 6379
  ports:
    - "127.0.0.1:4242:4242"
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:4242/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
    start_period: 30s   # Unleash runs DB migrations on first boot — needs longer start_period
```

**Key**: `start_period: 30s` — Unleash auto-runs DB migrations on first startup against Oracle; this takes 10-20s.

### 4. service.yaml pattern (Mystique depends_on)

```yaml
# services/flags/service.yaml
name: arc-flags
codename: mystique
image: ghcr.io/arc-framework/arc-flags:latest
tech: unleash
upstream: unleashorg/unleash-server
ports:
  - { port: 4242, protocol: http, description: "Unleash UI + REST API" }
health:
  endpoint: http://localhost:4242/health
  interval: 10s
depends_on:
  - oracle   # Postgres — feature flag state storage
  - sonic    # Redis — session cache
```

### 5. control.mk aggregate (mirrors data.mk)

```makefile
## control-up: Start all control plane services (Heimdall + Nick Fury + Mystique)
control-up:
    @docker network create arc_platform_net 2>/dev/null || true
    $(MAKE) heimdall-up --no-print-directory
    $(MAKE) nick-fury-up --no-print-directory
    $(MAKE) mystique-up --no-print-directory

## control-down: Stop all control plane services
control-down:
    $(MAKE) mystique-down --no-print-directory
    $(MAKE) nick-fury-down --no-print-directory
    $(MAKE) heimdall-down --no-print-directory

## control-health: Check health of all control plane services
control-health:
    @$(MAKE) heimdall-health --no-print-directory && \
     $(MAKE) nick-fury-health --no-print-directory && \
     $(MAKE) mystique-health --no-print-directory
```

Note: `control-up` starts in dependency order; `control-down` reverses it (Mystique first, then infra).

### 6. CI/CD — mirrors data-images.yml exactly

`control-images.yml` path filters:
- `services/gateway/**` → build-heimdall
- `services/secrets/**` → build-nick-fury
- `services/flags/**` → build-mystique

`control-release.yml` tag format: `control/vX.Y.Z` → Docker tag `control-vX.Y.Z`

### 7. profiles.yaml update

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
    - heimdall       # ← ADD: gateway is foundational for any agent platform

reason:
  services:
    - cortex
    - flash
    - strange
    - sonic
    - otel
    - tardis
    - nick-fury      # ← ADD: secrets management
    - mystique       # ← ADD: feature flags
```

## Constitution Check

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Zero-Dep CLI | N/A | No CLI changes |
| II | Platform-in-a-Box | PASS | `make control-up` boots all three; heimdall joins `think` profile |
| III | Modular Services | PASS | Each self-contained in own directory under `services/`; own service.yaml |
| IV | Two-Brain | PASS | Config-only upstream images — no language concern |
| V | Polyglot Standards | PASS | Same Dockerfile/compose/healthcheck structure as 003/005 |
| VI | Local-First | N/A | CLI only |
| VII | Observability | PASS | Traefik dashboard + /ping; OpenBao /v1/sys/health; Unleash /health |
| VIII | Security | PASS† | Heimdall uid 1000; Mystique uid 1000 (attempt); Nick Fury root documented (dev-mode-only) |
| IX | Declarative | N/A | CLI only |
| X | Stateful Ops | N/A | CLI only |
| XI | Resilience | PASS | Health checks with appropriate start_periods; Mystique depends_on oracle + sonic |
| XII | Interactive | N/A | CLI only |

†**Security note**: Nick Fury root deviation is intentional — OpenBao `-dev` mode is by-design insecure (ephemeral, known token). Documented in Dockerfile and `nick-fury-help`. Not a constitution violation given the explicit dev-only scope.

## Project Structure

```
arc-platform/
├── services/
│   ├── gateway/                              ← NEW (Heimdall / Traefik v3)
│   │   ├── Dockerfile                        # FROM traefik:v3; OCI + arc labels; USER 1000
│   │   ├── service.yaml                      # name, codename, ports 80+8090, health /ping
│   │   ├── docker-compose.yml                # port remap 80:8080; Docker socket ro; no volume
│   │   └── heimdall.mk                       # heimdall-up/down/health/logs/build/push/publish/...
│   ├── secrets/                              ← NEW (Nick Fury / OpenBao)
│   │   ├── Dockerfile                        # FROM openbao/openbao; OCI + arc labels; root documented
│   │   ├── service.yaml                      # name, codename, port 8200, health /v1/sys/health
│   │   ├── docker-compose.yml                # -dev mode; VAULT_DEV_ROOT_TOKEN_ID; no volume
│   │   └── nick-fury.mk                      # nick-fury-up/down/health/logs/build/push/publish/...
│   ├── flags/                                ← NEW (Mystique / Unleash)
│   │   ├── Dockerfile                        # FROM unleashorg/unleash-server; OCI + arc labels
│   │   ├── service.yaml                      # name, codename, port 4242, depends_on: oracle, sonic
│   │   ├── docker-compose.yml                # DATABASE_URL + REDIS_*; user 1000; start_period 30s
│   │   └── mystique.mk                       # mystique-up/down/health/logs/build/push/publish/...
│   ├── profiles.yaml                         # MODIFY — think += heimdall; reason += nick-fury, mystique
│   └── control.mk                            ← NEW (aggregate)
├── .github/workflows/
│   ├── control-images.yml                    ← NEW
│   └── control-release.yml                   ← NEW
└── Makefile                                  # MODIFY — include *.mk + publish-all
```

## Parallel Execution Strategy

```mermaid
gantt
    title 006-platform-control Implementation Phases
    dateFormat X
    axisFormat %s

    section Phase 1 — Foundation
    Update profiles.yaml (heimdall→think, fury+mystique→reason)  :p1, 0, 1

    section Phase 2 — Services (fully parallel)
    gateway/: Dockerfile + service.yaml + compose                 :p2a, after p1, 2
    secrets/: Dockerfile + service.yaml + compose                 :p2b, after p1, 2
    flags/: Dockerfile + service.yaml + compose                   :p2c, after p1, 2

    section Phase 3 — Make targets (parallel per service)
    heimdall.mk                                                    :p3a, after p2a, 1
    nick-fury.mk                                                   :p3b, after p2b, 1
    mystique.mk                                                    :p3c, after p2c, 1
    control.mk aggregate + Makefile includes                       :p3d, after p2a, 1

    section Phase 4 — CI/CD (parallel)
    control-images.yml workflow                                    :p4a, after p3d, 2
    control-release.yml workflow                                   :p4b, after p3d, 2

    section Phase 5 — Integration
    make control-up + make control-health                          :p5, after p4b, 1
    Docs & links update                                            :p5b, after p5, 1
```

**Parallelizable groups:**
- Phase 2: All three service directories are fully independent
- Phase 3: heimdall.mk + nick-fury.mk + mystique.mk — independent after Phase 2 deps
- Phase 4: control-images.yml + control-release.yml — independent of each other

## Tech Debt

| ID | Item | Rationale |
|----|------|-----------|
| TD-001 | Nick Fury production mode | OpenBao `-dev` mode is stateless and insecure. Production requires Raft-backed storage, TLS, and non-root user. Deferred to a future security hardening spec. |
| TD-002 | Heimdall TLS termination | No HTTPS in dev. Production needs TLS config (cert resolvers, ACME). Deferred. |
| TD-003 | Mystique admin credentials | Unleash auto-creates admin user on first boot; credentials are printed in logs. A future init task should configure an admin API token via env to avoid manual setup. |
| TD-004 | Traefik metrics scraping | Traefik exposes Prometheus metrics at `:8090/metrics`. When a dashboard requirement exists, add scrape job to OTEL collector (see 003 pattern). |

## Reviewer Checklist

- [ ] `make control-up` exits 0; all three containers in `healthy` state
- [ ] `make control-health` exits 0
- [ ] `make control-down` stops all three; no orphaned containers
- [ ] `make heimdall-up && make heimdall-health` works independently
- [ ] `make nick-fury-up && make nick-fury-health` works independently
- [ ] `make mystique-up && make mystique-health` works independently (requires oracle + sonic running)
- [ ] `curl http://localhost:8090/ping` returns `OK` (Traefik ping endpoint)
- [ ] Traefik dashboard accessible at `http://localhost:8090/dashboard/`
- [ ] `curl -H "X-Vault-Token: arc-dev-token" http://localhost:8200/v1/sys/health` returns HTTP 200
- [ ] `curl http://localhost:4242/health` returns HTTP 200
- [ ] `docker inspect arc-gateway | jq '.[0].Config.User'` confirms `"1000:1000"` or `"1000"`
- [ ] `docker inspect arc-flags | jq '.[0].Config.User'` confirms non-root or deviation documented
- [ ] Nick Fury root deviation documented in Dockerfile comment + `nick-fury-help` output
- [ ] All ports bind `127.0.0.1` only — verify with `docker compose ps`
- [ ] No persistent volumes for Heimdall or Nick Fury (stateless dev services)
- [ ] `services/profiles.yaml` `think` includes `heimdall`; `reason` includes `nick-fury` + `mystique`
- [ ] Makefile includes `heimdall.mk`, `nick-fury.mk`, `mystique.mk`, `control.mk`
- [ ] `publish-all` includes `heimdall-build heimdall-publish`, `nick-fury-build nick-fury-publish`, `mystique-build mystique-publish`
- [ ] `control-images.yml` path filters cover all three service dirs
- [ ] `control-release.yml` tag format `control/v*`; multi-platform amd64 + arm64
- [ ] All Dockerfiles have OCI + `arc.service.*` labels
- [ ] `CLAUDE.md` Service Codenames table updated (Nick Fury: Infisical → OpenBao)
- [ ] `.specify/config.yaml` `secrets` entry tech updated from `infisical` to `openbao`

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Traefik uid 1000 fails (needs root for some internal operation) | M | Fall back to root + document deviation like Pulsar in 003 |
| Mystique uid 1000 fails (writes to privileged path at startup) | M | Remove `user:` from compose; add comment documenting root deviation |
| Mystique startup fails because Oracle isn't ready | H | `start_period: 30s` + Unleash's built-in retry; `control-up` ensures oracle starts first via ordering |
| `wget` absent in openbao image | M | Fall back to bash `/dev/tcp` pattern (same as arc-vector-db) |
| Port 80 already bound on dev machine (other HTTP server) | M | Document in `heimdall-help`; user can change host port via compose override |
| Mystique DB migration creates tables in `arc` DB instead of separate DB | L | Verify `DATABASE_URL` points to `/unleash` DB path; Oracle Dockerfile may need `CREATE DATABASE unleash` init SQL |
| `arc_platform_net` not created before `make control-up` | H | `control-up` calls `docker network create arc_platform_net 2>/dev/null || true` first |
