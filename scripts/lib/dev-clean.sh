#!/usr/bin/env bash
# scripts/lib/dev-clean.sh — Remove containers, volumes, and orphans for a profile.
#
# Usage (from repo root):
#   scripts/lib/dev-clean.sh [PROFILE]   (default: think)
#   make dev-clean [PROFILE=reason]
#
# Prompts interactively before destroying any data.
# Requires: .make/registry.mk (run: make dev-regen)

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"
source "$SCRIPT_DIR/common.sh"

PROFILE="${SCRIPT_ARGS[0]:-${PROFILE:-think}}"
REGISTRY_MK=".make/registry.mk"

[[ -f "$REGISTRY_MK" ]] || die "$REGISTRY_MK not found — run: make dev-regen"

services=$("$SCRIPT_DIR/profile-services.sh" "$PROFILE") || exit 1

printf '%b!%b Removes containers, volumes, and orphans for profile '\''%s'\''.\n' \
  "$_YELLOW" "$_RESET" "$PROFILE" >&2
printf '  Services: %s\n' "$services" >&2

if ! confirm_action "Continue?"; then
  log_info "Aborted."
  exit 0
fi

seen_dirs=""
for svc in $services; do
  varname="$(echo "$svc" | tr '-' '_')"
  dir="$(grep "^SERVICE_${varname}_DIR" "$REGISTRY_MK" | sed 's/.*:=[[:space:]]*//' || true)"
  if [[ -n "$dir" ]] && ! echo "$seen_dirs" | grep -qw "$dir"; then
    seen_dirs="$seen_dirs $dir"
    docker compose -f "${dir}/docker-compose.yml" down --volumes --remove-orphans 2>/dev/null || true
    log_debug "Cleaned $dir"
  fi
done

log_success "Profile '$PROFILE' cleaned — data volumes removed"
