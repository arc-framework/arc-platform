#!/usr/bin/env bash
# scripts/lib/check-dev-prereqs.sh — Validate developer environment before starting services.
#
# Usage:
#   scripts/lib/check-dev-prereqs.sh
#
# Checks:
#   - Docker daemon is running
#   - Docker Compose v2 plugin is available (not legacy docker-compose)
#   - Required ports are free: 4222 6379 6650 8082 13133 8081
#
# Exit codes:
#   0  All prerequisites met
#   1  One or more checks failed
#
# Port → service mapping:
#   4222   messaging      (NATS client)
#   6379   cache          (Redis)
#   6650   streaming      (Pulsar broker)
#   8082   streaming      (Pulsar admin)
#   13133  friday-collector  (OTEL health)
#   8081   cortex         (API)

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# UI helpers — indented checklist lines (not the structured log format)
# ---------------------------------------------------------------------------

_ok()   { printf '  \033[0;32m\xe2\x9c\x93\033[0m %s\n' "$*"; }
_fail() { printf '  \033[0;31m\xe2\x9c\x97\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------------------
# Port → service mapping (bash 3.2 compatible — no declare -A)
# ---------------------------------------------------------------------------

port_to_service() {
  case "$1" in
    4222)  printf 'messaging' ;;
    6379)  printf 'cache' ;;
    6650)  printf 'streaming' ;;
    8082)  printf 'streaming' ;;
    13133) printf 'friday-collector' ;;
    8081)  printf 'cortex' ;;
    *)     printf 'unknown' ;;
  esac
}

REQUIRED_PORTS=(4222 6379 6650 8082 13133 8081)

# ---------------------------------------------------------------------------
# Port check — POSIX-compatible via /dev/tcp; falls back to nc
# ---------------------------------------------------------------------------

check_port() {
  local port="$1"
  # /dev/tcp is a bash built-in; redirect stderr to suppress the "connection
  # refused" message; if the connection succeeds the port is occupied.
  if (echo >/dev/tcp/localhost/"$port") 2>/dev/null; then
    return 1  # port in use
  fi
  return 0    # port free
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

printf '\xe2\x86\x92 Checking developer prerequisites...\n'

FAILED=0

# --- Docker daemon ---
if docker info > /dev/null 2>&1; then
  _ok "Docker daemon running"
else
  _fail "Docker daemon not running"
  FAILED=1
fi

# --- Docker Compose v2 ---
if docker compose version > /dev/null 2>&1; then
  _ok "Docker Compose v2 available"
else
  _fail "Docker Compose v2 not available (install the docker compose plugin)"
  FAILED=1
fi

# --- Required ports ---
for port in "${REQUIRED_PORTS[@]}"; do
  svc="$(port_to_service "$port")"
  if check_port "$port"; then
    _ok "Port $port free ($svc)"
  else
    _fail "Port $port already in use (required by $svc)"
    FAILED=1
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if [[ "$FAILED" -eq 0 ]]; then
  printf '\033[0;32m\xe2\x9c\x93\033[0m All prerequisites met\n'
  exit 0
else
  printf '\033[0;31m\xe2\x9c\x97\033[0m Prerequisites failed \xe2\x80\x94 fix the issues above and retry\n'
  exit 1
fi
