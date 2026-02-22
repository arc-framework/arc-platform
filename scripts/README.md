# scripts/

Utility scripts for the A.R.C. platform. All scripts follow the standards below.

> **Scope**: These standards apply to `scripts/` only. SpecKit scripts in `.specify/scripts/` have their own conventions.

---

## 📦 Script Catalog

| Script | Safety Tier | Description | Usage |
|--------|-------------|-------------|-------|
| `delete-org-packages.sh` | Destructive | Delete all container images from a GitHub org | `./scripts/delete-org-packages.sh [--no-dry-run] [ORG]` |
| `generate-pr-description.sh` | Read-only | Generate monorepo-aware PR description from branch changes | `./scripts/generate-pr-description.sh [BASE_BRANCH]` |

### Makefile Targets

Run via `make -C scripts <target>` or `cd scripts && make <target>`:

| Target | Description |
|--------|-------------|
| `help` | Show available targets |
| `list` | List all scripts with descriptions |
| `check` | Validate all scripts (syntax + shellcheck) |
| `packages-list` | Dry-run preview of org container packages |
| `packages-delete` | Delete all packages (triggers safety gates) |
| `pr` | Generate a PR description from branch changes |
| `pr-json` | Generate PR description in JSON mode |
| `permissions` | Ensure all scripts are `chmod +x` |

---

## 📏 Standards

### 1. Source `common.sh`

Every script must source the shared library as its first action after the shebang:

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"
source "$SCRIPT_DIR/lib/common.sh"
```

This gives you: logging, confirmation helpers, dependency checks, cleanup traps, and standard flag parsing.

### 2. Logging

Use the provided log functions. Never use raw `echo` for operational output.

```bash
log_info    "Starting operation..."
log_warn    "Config not found, using defaults"
log_error   "API returned 403"
log_success "Completed successfully"
log_debug   "Response payload: $data"   # only shown with --verbose
die         "Unrecoverable failure"     # logs + exits 1
```

**Format**: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [script-name] message`

- Color auto-disabled when output is piped or `--no-color` is set
- `--json` mode switches to JSON-lines format
- `--verbose` / `-v` enables `log_debug` output
- All log output goes to **stderr** so stdout stays clean for data

### 3. Standard Flags

These flags are parsed automatically by `common.sh`. Do not re-implement them.

| Flag | Env Override | Default | Effect |
|------|-------------|---------|--------|
| `--dry-run` | `DRY_RUN=true` | `true` | Safe preview mode (always the default) |
| `--no-dry-run` | `DRY_RUN=false` | — | Execute for real |
| `--verbose` / `-v` | `VERBOSE=true` | `false` | Show debug-level logs |
| `--json` | `JSON_OUTPUT=true` | `false` | JSON-lines output |
| `--no-color` | `NO_COLOR=1` | — | Disable color output |
| `--help` / `-h` | — | — | Show usage |

Script-specific args remain in the `SCRIPT_ARGS` array after common flags are stripped.

### 4. 🛡️ Safety Tiers

Every script falls into one of these tiers:

| Tier | Rules | Example |
|------|-------|---------|
| **Read-only** | No confirmation needed. Can run freely. | Health checks, status reports |
| **Mutating** | Dry-run default. `confirm_action` before changes. | Config generators, file movers |
| **Destructive** | Dry-run default + safety pin + typed confirmation + user allowlist. | Package deletion, data wipes |

#### Destructive Script Requirements

```bash
# 1. Check user is authorized
require_allowed_user "dgtalbug"

# 2. Require safety pin env var
require_safety_pin "ARC_CONFIRM_DESTRUCTIVE"

# 3. Typed confirmation (must type exact value)
confirm_destructive "$ORG" "org name"
```

### 5. Help / Usage

Define a `usage()` function before sourcing `common.sh`. The library calls it when `--help` is passed.

```bash
usage() {
  cat <<EOF
Usage: $0 [OPTIONS] <org>

Delete all container images from a GitHub organization.

Arguments:
  <org>    GitHub organization name (default: arc-framework)

Options:
  --no-dry-run   Execute deletions (default is dry-run)
  --verbose      Show debug output
  --json         JSON output mode
  --no-color     Disable colors
  --help         Show this help

Safety:
  Requires ARC_CONFIRM_DESTRUCTIVE=1 and user in allowlist.

Examples:
  $0 arc-framework                              # dry-run preview
  ARC_CONFIRM_DESTRUCTIVE=1 $0 --no-dry-run     # actually delete
EOF
  exit 0
}
```

### 6. Dependency Checks

Validate required tools at the top of the script, not when they fail mid-execution.

```bash
require_cmd "gh" "jq"
require_gh_scope "read:packages" "delete:packages"
```

### 7. Cleanup

Register temp files for automatic cleanup on exit or error:

```bash
tmp=$(mktemp)
register_cleanup "$tmp"
```

### 8. Error Handling

- `set -euo pipefail` is enforced by `common.sh`
- Use `die "message"` for unrecoverable errors
- Guard arithmetic in subshells: `((count++)) || true`
- Always provide remediation steps in error messages

### 9. ✅ Conventions Checklist

Before merging a new script, verify:

- [ ] Sources `common.sh`
- [ ] Has a `usage()` function
- [ ] Uses `log_*` functions, not `echo`
- [ ] Dry-run is the default behavior
- [ ] Destructive actions use the full safety tier (allowlist + pin + confirmation)
- [ ] Dependencies checked with `require_cmd`
- [ ] Temp files registered with `register_cleanup`
- [ ] Script is executable (`chmod +x`)
- [ ] Added to the catalog table above
- [ ] Error messages include remediation steps

---

## 🆕 Writing a New Script

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

<description>

Options:
  --no-dry-run   Execute for real
  --verbose      Debug output
  --json         JSON output
  --help         Show help

Examples:
  $0                    # dry-run
  $0 --no-dry-run       # execute
EOF
  exit 0
}

source "$SCRIPT_DIR/lib/common.sh"

require_cmd "gh" "jq"

# --- Your logic here ---

ORG="${SCRIPT_ARGS[0]:-arc-framework}"

log_info "Starting operation for $ORG..."

if is_dry_run; then
  log_info "Would do things here..."
  dry_run_bail
fi

# Mutating/destructive work below
confirm_action "Proceed with operation?"
log_success "Done."
```

Then: `chmod +x scripts/your-script.sh` and add it to the catalog table above.
