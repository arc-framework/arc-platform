#!/usr/bin/env bash
# scripts/lib/common.sh — Shared library for all scripts/ utilities.
#
# Source this at the top of every script:
#   SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "$SCRIPT_DIR/lib/common.sh"
#
# Provides: logging, confirmation helpers, dependency checks, cleanup traps,
#           standard flag parsing (--dry-run, --verbose, --json, --no-color, --help).

set -euo pipefail

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

# BASH_SOURCE[-1] requires bash 4.3+. macOS ships bash 3.2, so use index math.
_SCRIPT_NAME="$(basename "${BASH_SOURCE[${#BASH_SOURCE[@]}-1]}" .sh)"
_CLEANUP_FILES=()
_COMMON_INITIALIZED=false

# Color support — auto-detect TTY, respect NO_COLOR convention
_setup_colors() {
  if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]] && [[ "${_NO_COLOR_FLAG:-false}" != "true" ]]; then
    _RED='\033[0;31m'
    _GREEN='\033[0;32m'
    _YELLOW='\033[0;33m'
    _BLUE='\033[0;34m'
    _GRAY='\033[0;90m'
    _BOLD='\033[1m'
    _RESET='\033[0m'
  else
    _RED='' _GREEN='' _YELLOW='' _BLUE='' _GRAY='' _BOLD='' _RESET=''
  fi
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [script-name] message

_log() {
  local level="$1" color="$2" msg="$3"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"

  if [[ "${JSON_OUTPUT:-false}" == "true" ]]; then
    printf '{"ts":"%s","level":"%s","script":"%s","msg":"%s"}\n' \
      "$ts" "$level" "$_SCRIPT_NAME" "$msg"
    return
  fi

  printf '%b[%s]%b %b[%-5s]%b %b[%s]%b %s\n' \
    "$_GRAY" "$ts" "$_RESET" \
    "$color" "$level" "$_RESET" \
    "$_BOLD" "$_SCRIPT_NAME" "$_RESET" \
    "$msg" >&2
}

log_info()    { _log "INFO"  "$_BLUE"   "$*"; }
log_warn()    { _log "WARN"  "$_YELLOW" "⚠ $*"; }
log_error()   { _log "ERROR" "$_RED"    "✗ $*"; }
log_success() { _log "OK"    "$_GREEN"  "✔ $*"; }

log_debug() {
  [[ "${VERBOSE:-false}" == "true" ]] && _log "DEBUG" "$_GRAY" "$*"
  return 0
}

# Print a fatal error and exit
die() {
  log_error "$*"
  exit 1
}

# ---------------------------------------------------------------------------
# Confirmation Helpers
# ---------------------------------------------------------------------------

# Simple y/n confirmation. Returns 0 if confirmed, 1 if declined.
confirm_action() {
  local prompt="$1"

  if [[ "${JSON_OUTPUT:-false}" == "true" ]]; then
    die "Cannot prompt for confirmation in --json mode. Use environment variables."
  fi

  printf '%b%s [y/N]: %b' "$_YELLOW" "$prompt" "$_RESET" >&2
  local answer
  read -r answer
  [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

# Destructive confirmation — must type a specific value to proceed.
# Usage: confirm_destructive "arc-framework" "org name"
confirm_destructive() {
  local expected="$1"
  local label="${2:-value}"

  if [[ "${JSON_OUTPUT:-false}" == "true" ]]; then
    die "Cannot prompt for confirmation in --json mode. Use environment variables."
  fi

  echo "" >&2
  printf '%b┌──────────────────────────────────────────────────┐%b\n' "$_RED" "$_RESET" >&2
  printf '%b│  🛑 WARNING: PERMANENT DESTRUCTIVE ACTION        │%b\n' "$_RED" "$_RESET" >&2
  printf '%b│  This action CANNOT be undone.                   │%b\n' "$_RED" "$_RESET" >&2
  printf '%b└──────────────────────────────────────────────────┘%b\n' "$_RED" "$_RESET" >&2
  echo "" >&2
  printf 'Type the %s %b%s%b to confirm: ' "$label" "$_BOLD" "$expected" "$_RESET" >&2
  local answer
  read -r answer

  if [[ "$answer" != "$expected" ]]; then
    die "Confirmation failed — expected '$expected', got '$answer'. Aborting."
  fi

  log_info "Confirmed by user."
}

# Check that a safety-pin environment variable is set.
# Usage: require_safety_pin "ARC_CONFIRM_DESTRUCTIVE"
require_safety_pin() {
  local var_name="$1"

  if [[ "${!var_name:-}" != "1" ]]; then
    local orig_args=""
    if [[ ${#ORIGINAL_ARGS[@]} -gt 0 ]]; then
      orig_args="${ORIGINAL_ARGS[*]}"
    fi
    log_error "Safety pin required: set $var_name=1 to proceed."
    log_error "Example: $var_name=1 $0 ${orig_args}"
    exit 1
  fi

  log_debug "Safety pin $var_name is set."
}

# ---------------------------------------------------------------------------
# User Allowlist
# ---------------------------------------------------------------------------

# Check that the current gh-authenticated user is in the allowed list.
# Usage: require_allowed_user "alice" "bob"
require_allowed_user() {
  local allowed_users=("$@")
  local current_user

  current_user=$(gh api user --jq '.login' 2>/dev/null || echo "")

  if [[ -z "$current_user" ]]; then
    die "Could not determine GitHub username. Run 'gh auth login'."
  fi

  for allowed in "${allowed_users[@]}"; do
    if [[ "$current_user" == "$allowed" ]]; then
      log_debug "User '$current_user' is authorized."
      return 0
    fi
  done

  log_error "User '$current_user' is not authorized to run this script."
  log_error "Authorized users: ${allowed_users[*]}"
  log_error "To request access, add your username and submit a PR."
  exit 1
}

# ---------------------------------------------------------------------------
# Dependency Checks
# ---------------------------------------------------------------------------

# Verify required commands are available.
# Usage: require_cmd "gh" "jq" "curl"
require_cmd() {
  local missing=()
  for cmd in "$@"; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing required commands: ${missing[*]}"
  fi

  log_debug "All required commands available: $*"
}

# Verify gh CLI has required token scopes.
# Usage: require_gh_scope "read:packages" "delete:packages"
require_gh_scope() {
  local scopes_output
  scopes_output=$(gh auth status 2>&1 || true)

  for scope in "$@"; do
    if ! echo "$scopes_output" | grep -q "$scope"; then
      log_error "Missing GitHub scope: $scope"
      log_error "Run: gh auth refresh -s $(IFS=,; echo "$*")"
      exit 1
    fi
  done

  log_debug "All required GitHub scopes present: $*"
}

# ---------------------------------------------------------------------------
# Cleanup / Trap
# ---------------------------------------------------------------------------

# Register a file or directory for cleanup on exit.
# Usage: register_cleanup "$tmpfile"
register_cleanup() {
  _CLEANUP_FILES+=("$1")
}

_run_cleanup() {
  if [[ ${#_CLEANUP_FILES[@]} -gt 0 ]]; then
    for f in "${_CLEANUP_FILES[@]}"; do
      [[ -n "$f" ]] && rm -rf "$f" 2>/dev/null
    done
  fi
}

trap _run_cleanup EXIT

# ---------------------------------------------------------------------------
# Dry-Run Helper
# ---------------------------------------------------------------------------

# Check if dry-run is active. Use at the top of destructive sections.
is_dry_run() {
  [[ "${DRY_RUN:-true}" == "true" ]]
}

# Print dry-run banner and exit.
dry_run_bail() {
  local orig_args=""
  if [[ ${#ORIGINAL_ARGS[@]} -gt 0 ]]; then
    orig_args="${ORIGINAL_ARGS[*]}"
  fi
  log_info "🏜️ DRY RUN — no changes were made."
  log_info "To execute, run with --no-dry-run: $0 --no-dry-run ${orig_args}"
  exit 0
}

# ---------------------------------------------------------------------------
# Standard Flag Parsing
# ---------------------------------------------------------------------------
# Parses and strips common flags from the argument list.
# Remaining args are stored in SCRIPT_ARGS for the script to consume.

DRY_RUN="${DRY_RUN:-true}"
VERBOSE="${VERBOSE:-false}"
JSON_OUTPUT="${JSON_OUTPUT:-false}"
_NO_COLOR_FLAG="false"
SCRIPT_ARGS=()
ORIGINAL_ARGS=("${@+$@}")

_parse_common_flags() {
  local args=("$@")

  for arg in "${args[@]}"; do
    case "$arg" in
      --dry-run)   DRY_RUN="true" ;;
      --no-dry-run) DRY_RUN="false" ;;
      --verbose|-v) VERBOSE="true" ;;
      --json)      JSON_OUTPUT="true" ;;
      --no-color)  _NO_COLOR_FLAG="true" ;;
      --help|-h)
        if declare -F usage &>/dev/null; then
          usage
        else
          echo "Usage: $0 [OPTIONS] [ARGS]"
          echo "  --dry-run      Dry run mode (default)"
          echo "  --no-dry-run   Execute for real"
          echo "  --verbose, -v  Enable debug output"
          echo "  --json         JSON output mode"
          echo "  --no-color     Disable colored output"
          echo "  --help, -h     Show this help"
        fi
        exit 0
        ;;
      *)
        SCRIPT_ARGS+=("$arg")
        ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
# Called automatically when this file is sourced.

_init_common() {
  if [[ "$_COMMON_INITIALIZED" == "true" ]]; then
    return
  fi
  _COMMON_INITIALIZED=true

  # Parse flags from the caller's arguments passed via ARC_SCRIPT_ARGS.
  # We word-split intentionally here — script args are simple flags/values.
  if [[ -n "${ARC_SCRIPT_ARGS:+x}" ]]; then
    # shellcheck disable=SC2086
    _parse_common_flags $ARC_SCRIPT_ARGS
  fi

  _setup_colors

  log_debug "common.sh initialized (dry_run=$DRY_RUN, verbose=$VERBOSE, json=$JSON_OUTPUT)"
}

_init_common
