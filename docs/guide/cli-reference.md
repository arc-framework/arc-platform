---
url: /arc-platform/docs/guide/cli-reference.md
---
# CLI Reference

The `arc` CLI manages the lifecycle of your A.R.C. workspace — initialization, configuration, and platform launch.

## `arc workspace init`

Initialize a new A.R.C. workspace in the current directory (or a specified path).

```bash
arc workspace init                    # Current directory
arc workspace init ./my-project       # Specific path
arc workspace init --force            # Reinitialize existing workspace
```

**Flags:**

| Flag | Description |
|------|-------------|
| `-f, --force` | Reinitialize an existing workspace |
| `--skip-gitignore` | Don't create/update `.gitignore` |
| `--tier <name>` | Set initial tier (`think`, `reason`, `ultra-instinct`) |

**What it creates:**

```
my-project/
├── arc.yaml          # Workspace manifest — source of truth
├── .env              # Environment variables and secrets
├── .gitignore        # Ignores generated files and secrets
└── .arc/
    ├── state/        # Workspace state (init time, last run)
    ├── data/         # Persistent data volumes
    └── generated/    # Generated configs — do not edit manually
```

***

## `arc run`

Launch the platform for the current workspace. Reads `arc.yaml`, resolves service dependencies, and starts all services.

```bash
arc run                               # Uses tier from arc.yaml (default: think)
arc run --profile think               # Core only — 7 services
arc run --profile reason              # Core + reasoning engine
arc run --profile ultra-instinct      # All capabilities
arc run -d                            # Background (detached) mode
arc run --generate-only               # Generate configs without launching
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--profile <name>` | Override the tier from `arc.yaml` |
| `-d, --detached` | Run in background |
| `--generate-only` | Generate `docker-compose.yml` without launching |
| `--no-validate` | Skip Docker availability checks |

**What it does:**

1. Reads `arc.yaml` manifest
2. Resolves the tier → capability set → service list
3. Generates `docker-compose.yml` in `.arc/generated/`
4. Validates Docker availability
5. Launches all configured services with health checks

***

## `arc workspace info`

Display current workspace state and configuration.

```bash
arc workspace info
arc workspace info --no-color
```

**Output includes:**

* Workspace root and manifest location
* Active tier and enabled capabilities
* State information (init time, last run)
* Recent operations log

***

## `arc workspace history`

Show operation history for the workspace.

```bash
arc workspace history                 # Full history
arc workspace history -n 10           # Last 10 operations
arc workspace history -t generate     # Only generation operations
arc workspace history -s failed       # Only failed operations
```

**Flags:**

| Flag | Description |
|------|-------------|
| `-n, --limit N` | Limit to N entries |
| `-t, --type TYPE` | Filter by type: `init`, `generate`, `run` |
| `-s, --status STATUS` | Filter by status: `success`, `failed` |
| `--no-color` | Disable colored output |

***

## Profile Reference

| Profile | Services started | RAM (min) | Use case |
|---------|-----------------|-----------|----------|
| `think` | Core (7 services) | 4 GB | Fast iteration, no LLM engine |
| `reason` | Core + Sherlock (8 services) | 6 GB | Standard AI development |
| `ultra-instinct` | Core + all capabilities (14+ services) | 12 GB | Full platform |
| `observe` | `think` + SigNoz UI | 8 GB | Local telemetry debugging (dev only) |

***

## Common Operations

```bash
# Start the platform (core + reasoning engine)
arc run --profile reason

# Check health of all services
make dev-health

# Tail logs from all services
make dev-logs

# Stop and clean up (volumes retained)
make dev-down

# Full teardown including volumes
make dev-clean
```

***

> **See also:** [arc.yaml Reference](/guide/arc-yaml-reference) for the full manifest schema.
