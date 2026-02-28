#!/usr/bin/env bash
# scripts/lib/profile-services.sh — Resolve a named profile to its service list.
#
# Usage (from repo root):
#   scripts/lib/profile-services.sh [PROFILE]   (default: think)
#
# Output: single line, space-separated service names to stdout.
# Exits 1 if .make/ files are missing or the profile is unknown.
#
# Requires: .make/profiles.mk and .make/registry.mk (run: make dev-regen)

set -euo pipefail

PROFILE="${1:-think}"
PROFILES_MK="${PROFILES_MK:-.make/profiles.mk}"
REGISTRY_MK="${REGISTRY_MK:-.make/registry.mk}"

for f in "$PROFILES_MK" "$REGISTRY_MK"; do
  if [[ ! -f "$f" ]]; then
    printf 'profile-services: %s not found — run: make dev-regen\n' "$f" >&2
    exit 1
  fi
done

profile_var="PROFILE_$(echo "$PROFILE" | tr '[:lower:]-' '[:upper:]_')_SERVICES"
services=$(grep "^${profile_var}" "$PROFILES_MK" | sed 's/.*:=[[:space:]]*//' || true)

if [[ -z "$services" ]]; then
  all_profiles=$(grep '^ALL_PROFILES' "$PROFILES_MK" | sed 's/.*:=[[:space:]]*//')
  printf 'profile-services: unknown profile "%s". Available: %s\n' "$PROFILE" "$all_profiles" >&2
  exit 1
fi

if [[ "$services" == "*" ]]; then
  services=$(grep '^ALL_SERVICES' "$REGISTRY_MK" | sed 's/.*:=[[:space:]]*//')
fi

printf '%s\n' "$services"
