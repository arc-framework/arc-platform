# arc.yaml Reference

`arc.yaml` is the workspace manifest read by the `arc` CLI. It declares the platform tier, optional capability overrides, and environment configuration for the current workspace.

## Deprecation Notice

> **DEPRECATED tier IDs** — the following tier names were used in early versions of the platform and are no longer valid:
>
> | Old ID | Renamed to |
> |--------|-----------|
> | `super-saiyan` | `think` |
> | `super-saiyan-blue` | `reason` |
>
> Workspaces using these old IDs will fail with an error. Update your `arc.yaml` to use the current tier names listed below. The `features` map (old-style capability flags) has been replaced by the `capabilities` list.

## Full Example

```yaml
# arc.yaml — A.R.C. Workspace Manifest
# Documentation: https://github.com/arc-framework/arc-platform/docs/guide/arc-yaml-reference

# Manifest format version — do not change
version: "1.0.0"

# Platform tier — selects the base service set
# Options: think | reason | ultra-instinct
tier: "reason"

# Opt-in capabilities — activate additional service groups on top of the tier
# Each entry here starts the services defined in services/profiles.yaml
capabilities:
  - observe     # SigNoz observability UI at :3301
  # - voice     # STT + TTS + realtime (requires reasoner capability)
  # - security  # OpenBao secrets + Unleash feature flags
  # - storage   # MinIO object storage

# Environment overrides (optional)
# Injected into all services at startup
# environment:
#   LOG_LEVEL: "debug"
#   LLM_PROVIDER: "anthropic"
#   LLM_MODEL: "claude-3-5-sonnet-20241022"
#   LLM_API_KEY: "sk-ant-..."
```

## `tier` Field

The tier selects the base set of services started by `arc run`. Choose the smallest tier that meets your needs — larger tiers pull more images and require more memory.

| Tier | Description | Services activated |
|------|-------------|-------------------|
| `think` | Core infrastructure only — fastest to start, no LLM engine. Use for front-end development, infra testing, or when LLM access is not needed. | messaging, cache, streaming, cortex, persistence, gateway, friday-collector |
| `observe` | `think` + SigNoz observability UI. Dev-only profile — not a product tier. Use via `make dev PROFILE=observe` for local telemetry debugging. | All `think` services + otel (SigNoz stack at :3301) |
| `reason` | Core + reasoning engine — standard development stack. Activates the `reasoner` capability automatically. Use when you need LLM inference. | All `think` services + reasoner |
| `ultra-instinct` | Full platform — all capabilities enabled. Activates reasoner, voice, observe, security, and storage. Use for integration testing or production staging. | All services |

Specify the tier with `arc workspace init --tier <name>` or edit `arc.yaml` directly.

## Tier → Services Matrix

| Service | `think` | `reason` | `ultra-instinct` | Capability |
|---------|---------|---------|-----------------|-----------|
| arc-gateway | yes | yes | yes | core |
| arc-messaging | yes | yes | yes | core |
| arc-streaming | yes | yes | yes | core |
| arc-cache | yes | yes | yes | core |
| arc-persistence | yes | yes | yes | core |
| arc-cortex | yes | yes | yes | core |
| arc-friday-collector | yes | yes | yes | core |
| arc-reasoner | no | yes | yes | reasoner |
| arc-realtime | no | no | yes | voice |
| arc-voice-agent | no | no | yes | voice |
| arc-friday (SigNoz) | no | no | yes | observe |
| arc-vault | no | no | yes | security |
| arc-flags | no | no | yes | security |
| arc-storage | no | no | yes | storage |

## `capabilities` Field

`capabilities` is a list of capability names to activate on top of the selected tier. Each capability starts one or more additional services.

```yaml
capabilities:
  - observe
  - security
```

Valid capability names (sourced from `services/profiles.yaml`):

| Capability | Services started | Notes |
|-----------|-----------------|-------|
| `reasoner` | arc-reasoner | LLM reasoning engine — OpenAI-compatible API at :8802. Already included in `reason` and `ultra-instinct` tiers. |
| `voice` | arc-realtime, arc-voice-agent | Voice agent (STT + TTS) at :8803. Requires `reasoner` capability. |
| `observe` | arc-friday (SigNoz stack) | Observability UI at :3301. Activates traces, metrics, and logs dashboard. |
| `security` | arc-vault, arc-flags | OpenBao secrets management at :8200 + Unleash feature flags at :4242. |
| `storage` | arc-storage | MinIO object storage at :9000/:9001. |

Capabilities compose freely. To run the reasoning engine plus observability:

```yaml
tier: "think"
capabilities:
  - reasoner
  - observe
```

## `version` Field

Always `"1.0.0"`. This is the manifest schema version, not the platform version. Do not change this field.

## `environment` Field

Optional map of environment variables injected into all services. Use this to configure provider API keys and log levels without modifying service Dockerfiles.

```yaml
environment:
  LOG_LEVEL: "debug"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4o"
  LLM_API_KEY: "sk-..."
```

Never commit API keys to `arc.yaml`. Use a `.env` file or your secrets manager (`arc-vault`) instead, and add `arc.yaml` to `.gitignore` if it contains credentials.
