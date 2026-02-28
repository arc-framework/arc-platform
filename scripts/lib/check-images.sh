#!/usr/bin/env bash
# scripts/lib/check-images.sh — Verify required images exist locally or pull them from the registry.
#
# Usage:
#   scripts/lib/check-images.sh <svc1> <svc2> ...
#
# For each service codename supplied, reads SERVICE_<n>_IMAGE from .make/registry.mk.
# If the image is found locally: ✓ (no pull needed).
# If not found locally: attempts docker pull.
# If pull fails: ✗ exits 1 with the failing image name.
#
# Exit codes:
#   0  All required images available
#   1  One or more images missing and unpullable
#
# Requires: .make/registry.mk to exist (run parse-registry.sh first).

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REGISTRY_MK="${REGISTRY_MK:-.make/registry.mk}"

if [[ ! -f "$REGISTRY_MK" ]]; then
  die "registry.mk not found at '$REGISTRY_MK' — run: scripts/lib/parse-registry.sh > .make/registry.mk"
fi

if [[ $# -eq 0 ]]; then
  die "Usage: check-images.sh <svc1> <svc2> ..."
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ok()   { printf '  \033[0;32m\xe2\x9c\x93\033[0m %s\n' "$*"; }
_fail() { printf '  \033[0;31m\xe2\x9c\x97\033[0m %s\n' "$*"; }
_pull() { printf '  \033[0;34m\xe2\x86\x93\033[0m %s\n' "$*"; }

_get_image() {
  local codename="$1"
  local varname
  varname="$(printf '%s' "$codename" | tr '-' '_')"
  grep "^SERVICE_${varname}_IMAGE" "$REGISTRY_MK" | sed 's/.*:=[[:space:]]*//'
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

printf '\xe2\x86\x92 Checking images for services: %s\n' "$*"

FAILED=0

for svc in "$@"; do
  image="$(_get_image "$svc")"

  if [[ -z "$image" ]]; then
    log_debug "No image registered for '$svc' — skipping"
    continue
  fi

  if docker image inspect "$image" > /dev/null 2>&1; then
    _ok "$image (local)"
  else
    _pull "Pulling $image..."
    if docker pull "$image" > /dev/null 2>&1; then
      _ok "$image (pulled)"
    else
      _fail "$image — not found locally or in registry (run: make publish-all OR make ${svc}-build)"
      FAILED=1
    fi
  fi
done

if [[ "$FAILED" -eq 0 ]]; then
  printf '\033[0;32m\xe2\x9c\x93\033[0m All images available\n'
  exit 0
else
  printf '\033[0;31m\xe2\x9c\x97\033[0m One or more images missing \xe2\x80\x94 build or publish them first\n'
  exit 1
fi
