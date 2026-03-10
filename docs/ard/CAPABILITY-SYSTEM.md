---
url: /arc-platform/docs/ard/CAPABILITY-SYSTEM.md
---
# ARD: Core + Capability Service Model

| Field     | Value |
|-----------|-------|
| Status    | Proposed |
| Date      | 2026-03-09 |
| Affects   | `arc-framework/arc-cli`, `services/profiles.yaml` |
| Supersedes| Feature-flags section of `CLI-PLATFORM-INTEGRATION.md` |

***

## Problem

The current tier model bundles all services together. `think` includes `reasoner`, making it impossible to run pure infrastructure without an LLM engine. There is no way to express "I want core infra + voice but not reasoner" — you have to take an entire tier preset.

As the platform grows, every new service needs a clear classification: is it infrastructure that other things depend on, or is it an opt-in intelligent capability?

***

## Decision: Two-Layer Model

### Layer 1 — Core

Fixed set of infrastructure services that start with every workspace. No user configuration needed. These are services that:

* Have no AI/ML logic
* Are depended on by 2 or more capabilities
* Would be needed in any production deployment

```
core: messaging, cache, streaming, cortex, persistence, gateway, friday-collector
```

### Layer 2 — Capabilities

Opt-in service groups. Each capability is a named bundle that activates one or more services. A capability may declare `requires` dependencies on other capabilities.

| Capability | Services | Requires |
|------------|----------|----------|
| `reasoner` | reasoner | — |
| `voice`    | realtime, voice | reasoner |
| `observe`  | otel | — |
| `security` | vault, flags | — |
| `storage`  | storage | — |

### Tiers — Capability Presets

Tiers remain as named convenience bundles. They map to a fixed set of capabilities. The `arc.yaml` `tier` field still works as before — it just resolves to core + a capability list.

| Tier | Capabilities included |
|------|-----------------------|
| `think` | *(none — core only)* |
| `reason` | reasoner |
| `ultra-instinct` | all capabilities |

### arc.yaml Shape (post-rewrite)

```yaml
version: "1.0.0"

# Tier selects a preset capability bundle.
# think         — core infrastructure only
# reason        — core + reasoner
# ultra-instinct — core + all capabilities
tier: "think"

# Add individual capabilities on top of the tier.
# Dependency capabilities are auto-resolved (e.g. voice pulls in reasoner).
capabilities:
  - voice
  - observe

# Per-service env overrides (optional)
# environment:
#   LLM_MODEL: gpt-4o
```

***

## Classification Rule for New Services

Every new service added to the platform must be classified at the time it is created:

**Core** if all of these are true:

* Generic infrastructure (database, broker, cache, proxy, collector)
* No AI/ML/business logic
* Depended on by 2+ capabilities or by the platform bootstrap

**Capability** if any of these is true:

* Contains LLM, AI, or business-specific logic
* Optional for most workspaces
* Builds on top of core services

**Examples:**

| Service | Classification | Reason |
|---------|---------------|--------|
| `arc-chaos` | Core | Infrastructure resilience tool, no AI logic |
| `arc-guard` | Capability | AI guardrails, optional, depends on reasoner |
| `arc-critic` | Capability | AI evaluation logic, async consumer |
| `arc-billing` | Capability | Business logic, reads usage events |
| `arc-gym` | Capability | ML training loop, optional |
| `arc-identity` | Core | Auth infrastructure depended on by all secure services |

***

## HLD — System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  arc.yaml                                                    │
│    tier: think                                               │
│    capabilities: [voice, observe]                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI: ResolveServices(tier, capabilities)                    │
│                                                              │
│  1. Load core services         (profiles.yaml → core)        │
│  2. Expand tier preset         (think → [])                  │
│  3. Expand capabilities        (voice → [realtime, voice],   │
│                                 observe → [otel])            │
│  4. Resolve requires chain     (voice requires reasoner →    │
│                                 pull in reasoner)            │
│  5. Transitive dep resolution  (existing Phase 3)            │
│                                                              │
│  Output: ordered service list                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Generator: render docker-compose from catalog entries       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
              docker compose up
```

***

## LLD — Required Changes

### `services/profiles.yaml` (platform repo)

Extend the file with `core:` and `capabilities:` sections. Tiers reference capability names.

```yaml
# ─── Core ────────────────────────────────────────────────────
# Always started. Not configurable.
core:
  services:
    - messaging
    - cache
    - streaming
    - cortex
    - persistence
    - gateway
    - friday-collector

# ─── Capabilities ─────────────────────────────────────────────
capabilities:
  reasoner:
    services: [reasoner]
    description: "LLM reasoning engine — OpenAI-compatible API"
  voice:
    services: [realtime, voice]
    description: "Voice agent — STT, TTS, LLM bridge"
    requires: [reasoner]
  observe:
    services: [otel]
    description: "Observability UI — SigNoz traces, metrics, logs"
  security:
    services: [vault, flags]
    description: "Secrets management + feature flags"
  storage:
    services: [storage]
    description: "Object storage — MinIO"

# ─── Tier Presets ──────────────────────────────────────────────
# Tiers are named capability bundles for convenience.
think:
  description: "Core infrastructure only"
  capabilities: []
reason:
  description: "Core + reasoning engine"
  capabilities: [reasoner]
ultra-instinct:
  description: "Core + all capabilities"
  capabilities: "*"

# ─── Dev-only (not a tier, not in arc.yaml) ───────────────────
observe:
  description: "think + SigNoz UI — local debugging"
  capabilities: [observe]
```

### `arc-framework/arc-cli` changes

#### `pkg/workspace/manifest/manifest.go`

```go
type Manifest struct {
    Version      string            `yaml:"version"`
    Tier         string            `yaml:"tier"`                   // required
    Capabilities []string          `yaml:"capabilities,omitempty"` // additional opt-ins
    Environment  map[string]string `yaml:"environment,omitempty"`
}

var validTiers        = []string{"think", "reason", "ultra-instinct"}
var validCapabilities = []string{"reasoner", "voice", "observe", "security", "storage"}
```

#### `pkg/workspace/services/mapping.go`

```go
func (m *Mapper) ResolveServices(tier string, extraCaps []string) ([]*ServiceDefinition, error) {
    profiles := loadProfiles(profilesData)

    // Step 1: core is always included
    services := m.servicesForNames(profiles.Core.Services)

    // Step 2: tier preset capabilities
    tierCaps := profiles.TierCapabilities(tier) // returns [] for think, [reasoner] for reason, etc.

    // Step 3: merge tier caps + explicit caps, deduplicate
    allCaps := dedupe(append(tierCaps, extraCaps...))

    // Step 4: expand capabilities, resolve requires chain
    for _, cap := range m.expandRequires(allCaps, profiles) {
        services = append(services, m.servicesForCapability(cap, profiles)...)
    }

    // Step 5: transitive dependency resolution (unchanged from today)
    return m.resolveDependencies(dedupe(services))
}
```

#### `pkg/scaffold/templates/arc.yaml.tmpl`

```yaml
version: "1.0.0"

# Tier — core infrastructure preset.
# think         — infrastructure only (messaging, cache, db, gateway, cortex)
# reason        — think + reasoner (LLM reasoning engine)
# ultra-instinct — think + all capabilities
tier: "{{.Tier}}"

# Capabilities — add specific capabilities on top of the tier.
# Available: reasoner, voice, observe, security, storage
# Note: voice automatically pulls in reasoner if not already included.
{{- if .Capabilities}}
capabilities:
{{- range .Capabilities}}
  - {{.}}
{{- end}}
{{- end}}

# Environment overrides (optional)
# environment:
#   LLM_MODEL: gpt-4o
```

#### `pkg/cli/workspace/init.go`

Interactive prompts:

1. Tier selection: `think` (default) / `reason` / `ultra-instinct`
2. Capability selection (multi-select, only shown for `think` tier): checkboxes for reasoner, voice, observe, security, storage

***

## Service Commands via CLI

### Problem

Operators currently need Make to run service operations (`make reasoner-test`, `make gateway-health`). The CLI has no way to target individual services.

### Design: `arc service <cmd> <service>`

The CLI reads service metadata from the catalog and executes commands directly — no Make dependency.

```
arc service up <service>        # docker compose up -d <service>
arc service down <service>      # docker compose down <service>
arc service health <service>    # GET catalog.health_endpoint
arc service logs <service>      # docker compose logs -f <service>
arc service restart <service>   # down + up
arc service test <service>      # runs service-specific test command (from catalog)
```

### Catalog extension — `commands:` block

Each service entry in the catalog gains an optional `commands:` block that maps logical command names to their implementation:

```yaml
reasoner:
  ...
  commands:
    test:
      type: exec          # exec inside container or local
      run: "uv run python -m pytest tests/ -q"
      workdir: "/app"
    lint:
      type: exec
      run: "uv run ruff check src/ && uv run mypy src/"
    health:
      type: http
      url: "http://localhost:8802/health"
      timeout: 5s

voice:
  ...
  commands:
    test:
      type: exec
      run: "uv run python -m pytest tests/ -q"
      workdir: "/app"
    health:
      type: http
      url: "http://localhost:8803/health"
      timeout: 5s
```

### CLI command dispatch

```go
// pkg/cli/service/commands.go

func runServiceCommand(cmd string, serviceName string) error {
    svc, err := catalog.GetService(serviceName)
    if err != nil { return err }

    command, ok := svc.Commands[cmd]
    if !ok {
        return fmt.Errorf("service %q has no %q command", serviceName, cmd)
    }

    switch command.Type {
    case "http":
        return checkHTTPEndpoint(command.URL, command.Timeout)
    case "exec":
        return dockerExec(svc.ArcImage, command.Run, command.Workdir)
    case "compose":
        return dockerCompose(cmd, svc.ArcImage)
    }
    return nil
}
```

### New CLI command tree

```
arc service
├── up <service>         # start a specific service
├── down <service>       # stop a specific service
├── restart <service>    # restart a specific service
├── health <service>     # check health endpoint
├── logs <service>       # stream logs
├── test <service>       # run tests (exec type command)
└── list                 # list all services with status
```

### Example usage

```bash
arc service health reasoner       # → GET http://localhost:8802/health
arc service test voice            # → uv run python -m pytest tests/ -q (in container)
arc service up voice              # → docker compose up -d arc-voice-agent
arc service logs reasoner         # → docker compose logs -f arc-reasoner
```

***

## Summary of All Changes Required

### Platform repo (`arc-platform`)

| File | Change |
|------|--------|
| `services/profiles.yaml` | Add `core:`, `capabilities:`, restructure tier entries |

### CLI repo (`arc-cli`)

| File | Change |
|------|--------|
| `pkg/workspace/manifest/manifest.go` | Add `Capabilities []string`, validate against allowlist |
| `pkg/workspace/services/mapping.go` | Replace `MapFeaturesToServices` with `ResolveServices(tier, caps)` |
| `pkg/workspace/services/data/profiles.yaml` | Embed updated profiles.yaml from platform |
| `pkg/scaffold/templates/arc.yaml.tmpl` | Add capabilities section |
| `pkg/cli/workspace/init.go` | Add capability multi-select prompt |
| `pkg/catalog/data/services.yaml` | Add `commands:` block to each service entry |
| `pkg/cli/service/` | New command group: `arc service up/down/health/logs/test/list` |
| `pkg/catalog/service.go` | Add `Commands map[string]ServiceCommand` to Service struct |
