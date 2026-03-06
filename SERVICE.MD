# A.R.C. Service Map

Primary naming now follows the operational sources of truth:

1. Root [Makefile](Makefile) target names for orchestration
2. `service.yaml` `name` fields for runtime identity
3. GHCR image names for build and deploy artifacts
4. `codename` as optional metadata only

Do not treat codenames as canonical service identifiers.

## Naming Rules

- Use `make <service>-help` targets as the operator-facing service keys.
- Use `arc-*` names when referring to running services and images.
- Use service directory names under `services/` for implementation location.
- Use codenames only as secondary documentation flavor.

## Authoritative Service Map

Derived from [Makefile](Makefile) includes and `services/*/service.yaml`.

| Make target        | Runtime service        | Image                                               | Path                    | Technology            | Notes                                         | Codename         |
| ------------------ | ---------------------- | --------------------------------------------------- | ----------------------- | --------------------- | --------------------------------------------- | ---------------- |
| `gateway`          | `arc-gateway`          | `ghcr.io/arc-framework/arc-gateway:latest`          | `services/gateway/`     | Traefik               | API gateway and ingress                       | Heimdall         |
| `flags`            | `arc-flags`            | `ghcr.io/arc-framework/arc-flags:latest`            | `services/flags/`       | Unleash               | Feature flags service                         | Mystique         |
| `vault`            | `arc-vault`            | `ghcr.io/arc-framework/arc-vault:latest`            | `services/secrets/`     | OpenBao               | Secrets management                            | Nick Fury        |
| `messaging`        | `arc-messaging`        | `ghcr.io/arc-framework/arc-messaging:latest`        | `services/messaging/`   | NATS                  | Low-latency messaging backbone                | Flash            |
| `streaming`        | `arc-streaming`        | `ghcr.io/arc-framework/arc-streaming:latest`        | `services/streaming/`   | Pulsar                | Durable event streaming                       | Strange          |
| `cache`            | `arc-cache`            | `ghcr.io/arc-framework/arc-cache:latest`            | `services/cache/`       | Redis                 | Cache and hot state                           | Sonic            |
| `persistence`      | `arc-persistence`      | `ghcr.io/arc-framework/arc-persistence:latest`      | `services/persistence/` | PostgreSQL + pgvector | Long-term state and SQL storage               | Oracle           |
| `storage`          | `arc-storage`          | `ghcr.io/arc-framework/arc-storage:latest`          | `services/storage/`     | MinIO                 | Object storage                                | Tardis           |
| `realtime`         | `arc-realtime`         | `ghcr.io/arc-framework/arc-realtime:latest`         | `services/realtime/`    | LiveKit               | Realtime media stack; includes sidecars below | Daredevil        |
| `reasoner`         | `arc-reasoner`         | `ghcr.io/arc-framework/arc-reasoner:latest`         | `services/reasoner/`    | FastAPI + LangGraph   | Reasoning engine                              | Sherlock         |
| `cortex`           | `arc-cortex`           | `ghcr.io/arc-framework/arc-cortex:latest`           | `services/cortex/`      | Go                    | Bootstrap/orchestration service               | Cortex           |
| `otel`             | `arc-friday`           | `ghcr.io/arc-framework/arc-friday:latest`           | `services/otel/`        | SigNoz stack          | Full observability stack                      | Friday           |
| `friday-collector` | `arc-friday-collector` | `ghcr.io/arc-framework/arc-friday-collector:latest` | `services/otel/`        | OTEL Collector        | Telemetry collector alias from OTEL stack     | Friday Collector |

## Realtime Sidecars

`realtime` is the operational unit exposed by [Makefile](Makefile), but it includes additional runtime services defined in [services/realtime/service.yaml](services/realtime/service.yaml):

| Runtime service        | Image                                               | Purpose              | Codename |
| ---------------------- | --------------------------------------------------- | -------------------- | -------- |
| `arc-realtime-ingress` | `ghcr.io/arc-framework/arc-realtime-ingress:latest` | RTMP ingest          | Sentry   |
| `arc-realtime-egress`  | `ghcr.io/arc-framework/arc-realtime-egress:latest`  | Recording and export | Scribe   |

## Planned Services Not Yet in Makefile

These were left out of the authoritative map on purpose because they do not yet exist as active Make targets or `services/*/service.yaml` entries.

They still matter, so they are tracked separately here as planned services.

| Planned runtime name | Expected role                      | Source of intent                                                                                                                                         | Current status | Notes                                                                   |
| -------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | ----------------------------------------------------------------------- |
| `arc-voice-agent`    | Voice orchestration service        | [docs/ard/VOICE-SYSTEM.md](docs/ard/VOICE-SYSTEM.md), [specs/016-voice-system/spec.md](specs/016-voice-system/spec.md)                                   | Planned        | Production voice service on top of `arc-realtime`                       |
| `arc-guard`          | Guardrails / policy enforcement    | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Referenced by nervous system; not yet present in `services/`            |
| `arc-critic`         | Response evaluation / critique     | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Async consumer of reasoning events                                      |
| `arc-gym`            | Training / reinforcement signals   | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Async training loop service                                             |
| `arc-billing`        | Usage metering and cost tracking   | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Reads token usage events                                                |
| `arc-db-vector`      | Dedicated vector retrieval service | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md), [specs/015-nervous-system/spec.md](specs/015-nervous-system/spec.md) | Planned        | Mentioned in architecture; not currently a concrete service directory   |
| `arc-identity`       | Identity and authentication        | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md)                                                                       | Planned        | Mentioned in framework service reference; not present in Makefile       |
| `arc-chaos`          | Chaos and resilience testing       | [docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md](docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md)                                                                       | Planned        | Target service for resilience stage, not yet implemented in `services/` |

### Why these are separated

- **Authoritative map** = what operators can run today from [Makefile](Makefile)
- **Planned services** = what architecture and specs say will exist, but is not runnable yet

This avoids mixing deployed reality with roadmap intent.

## Composite and Utility Targets

These are not standalone runtime services, but they are included by the root [Makefile](Makefile) as orchestration helpers:

| Target group              | Source                  | Purpose                                |
| ------------------------- | ----------------------- | -------------------------------------- |
| `dev-*`                   | [Makefile](Makefile)    | Profile startup, health, logs, cleanup |
| `data-*`                  | `services/data.mk`      | Aggregate data-layer workflows         |
| `control-*`               | `services/control.mk`   | Aggregate control-plane workflows      |
| `messaging-*`             | `services/messaging.mk` | Aggregate fast-path infra helpers      |
| `scripts-*` / `publish-*` | `scripts/scripts.mk`    | Build, publish, and support tasks      |

## Usage Examples

- `make reasoner-help`
- `make realtime-up`
- `make messaging-health`
- `make dev PROFILE=reason`

## Preferred References

Use these forms in docs and specs:

- `arc-reasoner`
- `arc-messaging`
- `arc-streaming`
- `arc-cache`
- `arc-persistence`
- `arc-realtime`

Avoid codename-first references in architecture, contracts, config defaults, and service maps.
