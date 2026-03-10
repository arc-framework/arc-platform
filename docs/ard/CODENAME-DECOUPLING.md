---
url: /arc-platform/docs/ard/CODENAME-DECOUPLING.md
---
# Service Naming Decoupling

> Status: Implemented
> Spec folder: `specs/014-decouple-service-codenames/`
> Source of truth: [Makefile](../../Makefile) and `services/*/service.yaml`

## Decision

Codenames are fun metadata. They are not service identity.

From this point forward, the platform uses functional service names and `arc-*` image names as the primary references in:

* architecture docs
* specifications and plans
* config defaults
* wire contracts
* operational runbooks
* service maps

Codenames may still appear in metadata fields and narrative docs, but only as secondary labels.

## Naming Hierarchy

When there is any ambiguity, use this order:

1. Root [Makefile](../../Makefile) target name
2. `service.yaml` `name`
3. GHCR image name
4. Service directory under `services/`
5. `codename` field

## What Changed

### Primary references now use service names

Use:

* `arc-reasoner`
* `arc-messaging`
* `arc-streaming`
* `arc-cache`
* `arc-persistence`
* `arc-storage`
* `arc-realtime`
* `arc-gateway`
* `arc-vault`
* `arc-flags`
* `arc-cortex`
* `arc-friday`
* `arc-friday-collector`

### Codenames are now secondary only

Allowed:

* `codename:` metadata in `service.yaml`
* optional secondary mention in prose
* sidecar annotations where useful for historical continuity

Not allowed as primary identifiers:

* package names
* config defaults
* DNS/container assumptions
* NATS subjects
* Pulsar topics
* service maps
* spec titles and main architecture references

## Authoritative Service Mapping

Derived from [Makefile](../../Makefile) includes and the current `service.yaml` files.

| Make target        | Primary runtime name   | Directory               | Image                                               | Codename metadata |
| ------------------ | ---------------------- | ----------------------- | --------------------------------------------------- | ----------------- |
| `gateway`          | `arc-gateway`          | `services/gateway/`     | `ghcr.io/arc-framework/arc-gateway:latest`          | Heimdall          |
| `flags`            | `arc-flags`            | `services/flags/`       | `ghcr.io/arc-framework/arc-flags:latest`            | Mystique          |
| `vault`            | `arc-vault`            | `services/secrets/`     | `ghcr.io/arc-framework/arc-vault:latest`            | Nick Fury         |
| `messaging`        | `arc-messaging`        | `services/messaging/`   | `ghcr.io/arc-framework/arc-messaging:latest`        | Flash             |
| `streaming`        | `arc-streaming`        | `services/streaming/`   | `ghcr.io/arc-framework/arc-streaming:latest`        | Strange           |
| `cache`            | `arc-cache`            | `services/cache/`       | `ghcr.io/arc-framework/arc-cache:latest`            | Sonic             |
| `persistence`      | `arc-persistence`      | `services/persistence/` | `ghcr.io/arc-framework/arc-persistence:latest`      | Oracle            |
| `storage`          | `arc-storage`          | `services/storage/`     | `ghcr.io/arc-framework/arc-storage:latest`          | Tardis            |
| `realtime`         | `arc-realtime`         | `services/realtime/`    | `ghcr.io/arc-framework/arc-realtime:latest`         | Daredevil         |
| `reasoner`         | `arc-reasoner`         | `services/reasoner/`    | `ghcr.io/arc-framework/arc-reasoner:latest`         | Sherlock          |
| `cortex`           | `arc-cortex`           | `services/cortex/`      | `ghcr.io/arc-framework/arc-cortex:latest`           | Cortex            |
| `otel`             | `arc-friday`           | `services/otel/`        | `ghcr.io/arc-framework/arc-friday:latest`           | Friday            |
| `friday-collector` | `arc-friday-collector` | `services/otel/`        | `ghcr.io/arc-framework/arc-friday-collector:latest` | Friday Collector  |

## Planned Services

Planned services should be documented, but they must not be mixed into the authoritative runtime map until they exist in [Makefile](../../Makefile) or have a concrete `service.yaml`.

Use a separate planned section for items such as:

* `arc-voice-agent`
* `arc-guard`
* `arc-critic`
* `arc-gym`
* `arc-billing`
* `arc-db-vector`
* `arc-identity`
* `arc-chaos`

That keeps documentation honest:

* **implemented** = operable now
* **planned** = architectural intent

## Realtime Sidecars

The `realtime` target is the operator-facing unit, but the runtime stack also includes:

| Runtime service        | Image                                               | Purpose          | Codename metadata |
| ---------------------- | --------------------------------------------------- | ---------------- | ----------------- |
| `arc-realtime-ingress` | `ghcr.io/arc-framework/arc-realtime-ingress:latest` | RTMP ingest      | Sentry            |
| `arc-realtime-egress`  | `ghcr.io/arc-framework/arc-realtime-egress:latest`  | Recording/export | Scribe            |

## Operational Guidance

Prefer these forms in all new docs:

* `arc-reasoner` instead of a codename-first label
* `arc-messaging` instead of a codename-first label
* `arc-streaming` instead of a codename-first label
* `arc-cache` instead of a codename-first label
* `arc-realtime` instead of a codename-first label

If a codename is included for readability, format it as secondary metadata, for example:

`arc-reasoner` (codename: Sherlock)

Not the other way around.

## Impact

This keeps naming stable across:

* implementation
* deployment
* contracts
* diagrams
* future service additions

It also removes the mismatch between historical codename-heavy docs and the actual operational model exposed by [Makefile](../../Makefile).
