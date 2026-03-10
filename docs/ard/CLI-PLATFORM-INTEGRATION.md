# ARD: CLI Tier System — Platform Profile Alignment

| Field     | Value |
|-----------|-------|
| Status    | Proposed |
| Date      | 2026-03-09 |
| Affects   | `arc-framework/arc-cli` |
| Relates to | `services/profiles.yaml`, `specs/016-voice-system` |

---

## Problem

The CLI and the platform use two overlapping but incompatible naming systems for capability levels.

### CLI tier system (current)

Defined in `pkg/workspace/formatter.go`:

```go
const (
    tierIDSuperSaiyan     = "super-saiyan"      // index 0
    tierIDSuperSaiyanBlue = "super-saiyan-blue" // index 1
    tierIDUltraInstinct   = "ultra-instinct"    // index 2
)
```

The `arc.yaml` manifest accepts one of these three strings as its `tier` field. The formatter maps each to a display name via the active profile (e.g. "Starter / Pro / Ultra" for the enterprise profile).

### Platform profile system (current)

Defined in `services/profiles.yaml`:

| Profile ID      | Type         | Description |
|-----------------|--------------|-------------|
| `think`         | **Tier**     | Core infra + reasoner — minimal working agent |
| `observe`       | Dev tool     | `think` + SigNoz UI — local debugging only |
| `reason`        | **Tier**     | Full dev stack — adds secrets, storage, realtime, voice |
| `ultra-instinct`| **Tier**     | All services |

`observe` is a developer convenience shortcut, not a product tier. It is not exposed in `arc.yaml`.

### The mismatch

| CLI tier ID         | Platform profile ID | Match? |
|---------------------|---------------------|--------|
| `super-saiyan`      | `think`             | No — name mismatch |
| `super-saiyan-blue` | `reason`            | No — name mismatch |
| `ultra-instinct`    | `ultra-instinct`    | **Yes** |

**Consequences today:**
- `arc.yaml` cannot reference `think` or `reason` — the generator only understands the Saiyan-themed IDs.
- Operators using `make dev PROFILE=think` and `arc workspace run` have no consistent vocabulary.
- `ultra-instinct` is the only tier that works in both systems today.

---

## Decision

Rename CLI tier IDs to match the platform profile names. Three tiers, same count as today — only the string constants change.

**New tier IDs:**

| Index | New tier ID     | Replaces            | What it activates |
|-------|-----------------|---------------------|-------------------|
| 0     | `think`         | `super-saiyan`      | Core infra + reasoner |
| 1     | `reason`        | `super-saiyan-blue` | Full dev stack + realtime + voice |
| 2     | `ultra-instinct`| `ultra-instinct`    | All services |

The `observe` profile remains available via `make dev PROFILE=observe` for local telemetry debugging but is **not** a tier and does not appear in `arc.yaml`.

---

## Required CLI Changes

All changes are in `arc-framework/arc-cli`. The platform repo is read-only for this ARD.

### 1. `pkg/workspace/formatter.go`

Replace the 3-constant block and `getTierIndex()`:

```go
// Before
const (
    tierIDSuperSaiyan     = "super-saiyan"
    tierIDSuperSaiyanBlue = "super-saiyan-blue"
    tierIDUltraInstinct   = "ultra-instinct"
)

func getTierIndex(tierID string) int {
    switch tierID {
    case tierIDSuperSaiyan:     return 0
    case tierIDSuperSaiyanBlue: return 1
    case tierIDUltraInstinct:   return 2
    default:                    return -1
    }
}
```

```go
// After
const (
    tierIDThink         = "think"
    tierIDReason        = "reason"
    tierIDUltraInstinct = "ultra-instinct"
)

func getTierIndex(tierID string) int {
    switch tierID {
    case tierIDThink:         return 0
    case tierIDReason:        return 1
    case tierIDUltraInstinct: return 2
    default:                  return -1
    }
}
```

`getGenericTierName()` is unchanged — it already handles indices 0, 1, 2.

### 2. `pkg/workspace/manifest/manifest.go`

Add an explicit allowlist for tier validation:

```go
var validTierIDs = map[string]bool{
    "think":          true,
    "reason":         true,
    "ultra-instinct": true,
}
```

### 3. `pkg/ui/theme/embedded/profiles/*.yaml`

`tier_names` arrays stay at 3 entries — no structural change needed. Only the *meaning* of each index shifts. The existing display names (Starter / Pro / Ultra, Padawan / Knight / Master, etc.) continue to map correctly to the new IDs.

Example enterprise profile — no change required:

```yaml
tier_names:
  - Starter    # index 0 → think
  - Pro        # index 1 → reason
  - Ultra      # index 2 → ultra-instinct
```

### 4. `pkg/scaffold/templates/arc.yaml.tmpl`

Change the default tier from `ultra-instinct` to `think` so new workspaces start with the minimal stack:

```yaml
# Before
tier: "ultra-instinct"

# After
tier: "think"
```

### 5. `pkg/workspace/services/registry.go` (optional cleanup)

The legacy `GetMasterServiceTable()` function predates the embedded catalog. It contains hardcoded service definitions that duplicate `pkg/catalog/data/services.yaml`. Consider deprecating it in the same PR.

---

## arc.yaml Reference (post-change)

```yaml
version: "1.0.0"

# Tier selects which platform profile (set of services) to activate.
# Maps directly to `make dev PROFILE=<tier>` and services/profiles.yaml.
#
# think         — core infra + reasoner (default, fastest to start)
# reason        — full dev stack: think + secrets + storage + realtime + voice
# ultra-instinct — everything
#
# Note: `observe` (think + SigNoz UI) is available via `make dev PROFILE=observe`
#       for local debugging but is not a tier and does not appear here.
tier: "think"

features:
  voice: false
  security: false
  observability: false
  chaos: false
```

---

## Tier → Service Map

| Service          | think | reason | ultra-instinct |
|------------------|:-----:|:------:|:--------------:|
| messaging        | ✓     | ✓      | ✓ |
| cache            | ✓     | ✓      | ✓ |
| streaming        | ✓     | ✓      | ✓ |
| cortex           | ✓     | ✓      | ✓ |
| persistence      | ✓     | ✓      | ✓ |
| gateway          | ✓     | ✓      | ✓ |
| friday-collector | ✓     | ✓      | ✓ |
| reasoner         | ✓     | ✓      | ✓ |
| otel             |       | ✓      | ✓ |
| storage          |       | ✓      | ✓ |
| secrets (vault)  |       | ✓      | ✓ |
| flags            |       | ✓      | ✓ |
| realtime         |       | ✓      | ✓ |
| voice            |       | ✓      | ✓ |

---

## `arc workspace init` — Rewrite Design

> Full design detail: [docs/ard/CAPABILITY-SYSTEM.md](CAPABILITY-SYSTEM.md)

### Why it needs a rewrite

`arc workspace init` creates an `arc.yaml` with a `tier` field and a `features` map. The problem: the generator **never reads `tier`**. Service selection is driven entirely by `features` flags via `MapFeaturesToServices()`. The tier field is decorative metadata.

The rewrite introduces two concepts: **core** (always-on infrastructure) and **capabilities** (opt-in intelligent services). Tiers become named capability presets for convenience.

### New model

```
Core (always started):
  messaging, cache, streaming, cortex, persistence, gateway, friday-collector

Capabilities (opt-in):
  reasoner  → LLM reasoning engine
  voice     → realtime + voice agent (requires: reasoner)
  observe   → SigNoz UI
  security  → vault + flags
  storage   → MinIO

Tiers (presets):
  think         = core only
  reason        = core + [reasoner]
  ultra-instinct = core + all capabilities
```

### New flow

```
arc.yaml
  tier: "think"
  capabilities: [voice, observe]   ← replaces features map

ResolveServices(tier, capabilities)
  Step 1: core services (fixed)
  Step 2: tier preset capabilities → [reasoner] for reason, [] for think
  Step 3: explicit capabilities → expand + resolve requires chain
  Step 4: transitive dep resolution (existing Phase 3, unchanged)
  → docker-compose.yml
```

### Changes required in `arc-framework/arc-cli`

#### `pkg/workspace/manifest/manifest.go`

```go
type Manifest struct {
    Version      string            `yaml:"version"`
    Tier         string            `yaml:"tier"`                   // required
    Capabilities []string          `yaml:"capabilities,omitempty"` // opt-in
    Environment  map[string]string `yaml:"environment,omitempty"`
}

var validTiers        = []string{"think", "reason", "ultra-instinct"}
var validCapabilities = []string{"reasoner", "voice", "observe", "security", "storage"}
```

#### `pkg/workspace/services/mapping.go`

Replace `MapFeaturesToServices()` with `ResolveServices()`:

```go
//go:embed data/profiles.yaml
var profilesData []byte

func (m *Mapper) ResolveServices(tier string, caps []string) ([]*ServiceDefinition, error) {
    profiles := loadProfiles(profilesData)

    // Step 1: core always included
    services := m.servicesForNames(profiles.Core.Services)

    // Step 2: tier preset capabilities
    tierCaps := profiles.TierCapabilities(tier)

    // Step 3: merge + expand requires chain
    allCaps := m.expandRequires(dedupe(append(tierCaps, caps...)), profiles)
    for _, cap := range allCaps {
        services = append(services, m.servicesForCapability(cap, profiles)...)
    }

    // Step 4: transitive dep resolution (unchanged)
    return m.resolveDependencies(dedupe(services))
}
```

#### `pkg/workspace/services/data/profiles.yaml`

Embed the platform's `services/profiles.yaml` (new capability-aware format):

```yaml
# Copied from arc-platform/services/profiles.yaml
# See: services/profiles.yaml for full source
core:
  services: [messaging, cache, streaming, cortex, persistence, gateway, friday-collector]
capabilities:
  reasoner: {services: [reasoner]}
  voice:    {services: [realtime, voice], requires: [reasoner]}
  observe:  {services: [otel]}
  security: {services: [vault, flags]}
  storage:  {services: [storage]}
think:
  capabilities: []
reason:
  capabilities: [reasoner]
ultra-instinct:
  capabilities: '*'
```

#### `pkg/scaffold/templates/arc.yaml.tmpl`

```yaml
version: "1.0.0"

# Tier — selects a capability preset.
# think         — core infrastructure only (fastest to start)
# reason        — core + reasoner (LLM engine)
# ultra-instinct — core + all capabilities
tier: "{{.Tier}}"

# Capabilities — add specific capabilities on top of the tier.
# Available: reasoner, voice, observe, security, storage
# Note: voice automatically includes reasoner.
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

1. Replace tier prompt choices: `think` (default) / `reason` / `ultra-instinct`
2. For `think` tier: show capability multi-select (reasoner, voice, observe, security, storage)
3. For `reason`+: show additional capability multi-select (voice, observe, security, storage)

---

## CLI Service Catalog — Stale Entries

The following entries in `pkg/catalog/data/services.yaml` have drifted from the platform and need updating before the workspace rewrite ships:

| Catalog field | Current (stale) | Correct |
|---------------|-----------------|---------|
| `sherlock.arc_image` | `arc-brain` | `arc-reasoner` |
| `sherlock.ports[0].host` | `8000` | `8802` |
| `sherlock.dependencies` | `[oracle, sonic, cerebro]` | `[persistence, messaging, streaming, friday-collector]` |
| `scarlett.arc_image` | `arc-voice-agent` | `arc-voice-agent` ✓ |
| `scarlett.ports[0].host` | `8010` | `8803` |
| `scarlett.dependencies` | `[sherlock, daredevil]` | `[messaging, streaming, realtime, friday-collector, cache]` |
| `scarlett.released` | `false` | `false` (keep until voice make target registered) |

The full corrected entries are in [SERVICE.MD — CLI Catalog Entries](../../SERVICE.MD#cli-service-catalog-entries-source-of-truth).

---

## Migration Notes

- **`ultra-instinct` is unchanged** — existing `arc.yaml` files using it continue to work.
- **`super-saiyan` / `super-saiyan-blue`** become unrecognized after this change. `getTierIndex()` returns `-1`, falling back to `"Unknown Tier"` display. A deprecation warning in the manifest validator is recommended before removing support.
- **`observe` profile** stays in `services/profiles.yaml` and is fully usable via `make dev PROFILE=observe`. It is simply not promoted to a tier.
