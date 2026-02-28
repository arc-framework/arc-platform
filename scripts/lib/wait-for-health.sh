#!/usr/bin/env bash
# scripts/lib/wait-for-health.sh — Poll a health endpoint until healthy or timeout.
#
# Usage:
#   scripts/lib/wait-for-health.sh <codename> <endpoint> [timeout_seconds]
#
#   <codename>        Service name used in log messages (e.g. flash, sonic)
#   <endpoint>        HTTP URL (http:// or https://) polled via curl -sf,
#                     OR any shell command (e.g. "docker exec arc-sonic redis-cli ping")
#                     polled via eval.
#   [timeout_seconds] Optional. Default: 120.
#
# Exit codes:
#   0  Service became healthy within the timeout window
#   1  Timeout expired — service never responded healthy
#
# Examples:
#   scripts/lib/wait-for-health.sh flash "http://localhost:8222/healthz" 60
#   scripts/lib/wait-for-health.sh sonic "docker exec arc-sonic redis-cli ping" 30
#   scripts/lib/wait-for-health.sh cortex "http://localhost:8081/health"
#
# Requires: curl (for HTTP endpoints), bash 3.2+
# No external deps beyond what is already required by existing Makefiles.

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

if [[ $# -lt 2 ]]; then
  printf 'Usage: %s <codename> <endpoint> [timeout_seconds]\n' "$0" >&2
  exit 1
fi

CODENAME="$1"
ENDPOINT="$2"
TIMEOUT="${3:-120}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Returns 0 if the endpoint is healthy, 1 otherwise.
_check_health() {
  case "$ENDPOINT" in
    http://*|https://*)
      curl -sf "$ENDPOINT" > /dev/null 2>&1
      ;;
    *)
      eval "$ENDPOINT" > /dev/null 2>&1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Poll loop
# ---------------------------------------------------------------------------

log_info "Waiting for $CODENAME..."

elapsed=0
interval=2

while [[ "$elapsed" -lt "$TIMEOUT" ]]; do
  if _check_health; then
    log_success "$CODENAME healthy"
    exit 0
  fi

  elapsed=$(( elapsed + interval ))
  sleep "$interval"
done

# Final attempt at exactly the timeout boundary
if _check_health; then
  log_success "$CODENAME healthy"
  exit 0
fi

log_error "$CODENAME did not become healthy after ${TIMEOUT}s"
exit 1
