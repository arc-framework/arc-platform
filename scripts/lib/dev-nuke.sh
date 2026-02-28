#!/usr/bin/env bash
# scripts/lib/dev-nuke.sh — Remove containers, volumes, images, and orphans for a profile.
#
# Usage (from repo root):
#   scripts/lib/dev-nuke.sh [PROFILE]   (default: think)
#   make dev-nuke [PROFILE=reason]
#
# DESTRUCTIVE: removes local images — must be rebuilt or re-pulled afterward.
# Requires typing the profile name to confirm.
# Requires: .make/registry.mk (run: make dev-regen)

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"
source "$SCRIPT_DIR/common.sh"

PROFILE="${SCRIPT_ARGS[0]:-${PROFILE:-think}}"
REGISTRY_MK=".make/registry.mk"

[[ -f "$REGISTRY_MK" ]] || die "$REGISTRY_MK not found — run: make dev-regen"

services=$("$SCRIPT_DIR/profile-services.sh" "$PROFILE") || exit 1

log_warn "Destroys ALL state for profile '$PROFILE': containers, volumes, images, orphans."
log_warn "Images will need to be rebuilt or re-pulled. This is unrecoverable."
printf '  Services: %s\n' "$services" >&2

confirm_destructive "$PROFILE" "profile name"

seen_dirs=""
for svc in $services; do
  varname="$(echo "$svc" | tr '-' '_')"
  dir="$(grep "^SERVICE_${varname}_DIR" "$REGISTRY_MK" | sed 's/.*:=[[:space:]]*//' || true)"
  if [[ -n "$dir" ]] && ! echo "$seen_dirs" | grep -qw "$dir"; then
    seen_dirs="$seen_dirs $dir"
    docker compose -f "${dir}/docker-compose.yml" down --volumes --remove-orphans --rmi local 2>/dev/null || true
    log_debug "Nuked $dir"
  fi
done

log_success "Profile '$PROFILE' nuked — rebuild with: make dev"
