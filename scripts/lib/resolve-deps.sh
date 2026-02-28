#!/usr/bin/env bash
# scripts/lib/resolve-deps.sh — Resolve service startup order via Kahn's topological sort.
#
# Usage (from repo root):
#   scripts/lib/resolve-deps.sh <codename> [<codename> ...]
#
# Stdout: One line per startup layer (space-separated codenames).
# Stderr: Log messages via common.sh helpers.
#
# Exit codes:
#   0  Success — layers printed to stdout
#   1  Unregistered dependency or circular dependency detected
#
# Requires: awk, grep, sed (POSIX), bash 3.2+
# No external deps.

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REGISTRY_MK="${REGISTRY_MK:-.make/registry.mk}"

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
  die "Usage: resolve-deps.sh <codename> [<codename> ...]"
fi

if [[ ! -f "$REGISTRY_MK" ]]; then
  die "Registry file not found at '$REGISTRY_MK'. Run scripts/lib/parse-registry.sh first."
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Convert codename to Make variable name segment (hyphens -> underscores)
_varname() {
  echo "$1" | tr '-' '_'
}

# Get the ALL_SERVICES list from registry.mk (space-separated)
_get_all_services() {
  grep "^ALL_SERVICES[[:space:]]*:=" "$REGISTRY_MK" \
    | sed 's/^ALL_SERVICES[[:space:]]*:=[[:space:]]*//' \
    | sed 's/[[:space:]]*$//'
}

# Get the depends_on list for a codename from registry.mk (space-separated, may be empty)
_get_deps() {
  local codename="$1"
  local varname
  varname="$(_varname "$codename")"
  grep "^SERVICE_${varname}_DEPENDS[[:space:]]*:=" "$REGISTRY_MK" 2>/dev/null \
    | sed 's/^[^:]*:=[[:space:]]*//' \
    | sed 's/[[:space:]]*$//'
}

# Check if $1 is in a space-separated list $2 (returns 0=yes, 1=no)
_in_list() {
  local needle="$1"
  local list="$2"
  local item
  for item in $list; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

# ---------------------------------------------------------------------------
# Parallel indexed arrays (bash 3.2 compatible — no declare -A)
#
# State is stored in parallel indexed arrays indexed by position:
#   svc_names[i]    — codename at index i
#   svc_indegree[i] — in-degree count for svc_names[i]
#   svc_deps[i]     — space-separated list of within-input deps for svc_names[i]
#
# Lookup helpers use a linear scan (input sets are small, typically < 20 items).
# ---------------------------------------------------------------------------

input_services="$*"
all_services="$(_get_all_services)"

log_debug "Input services: $input_services"
log_debug "Registered services: $all_services"

svc_names=()
svc_indegree=()
svc_deps=()

# Index all input services into the arrays
_svc_index() {
  local needle="$1"
  local i=0
  for name in "${svc_names[@]+"${svc_names[@]}"}"; do
    [[ "$name" == "$needle" ]] && echo "$i" && return 0
    i=$(( i + 1 ))
  done
  echo "-1"
}

# Build arrays
for svc in $input_services; do
  svc_names+=("$svc")
  svc_indegree+=(0)
  svc_deps+=("")
done

# Populate in-degrees and deps lists
total=${#svc_names[@]}
for (( i = 0; i < total; i++ )); do
  svc="${svc_names[$i]}"
  raw_deps="$(_get_deps "$svc")"
  log_debug "Service '$svc' raw depends_on: '$raw_deps'"

  for dep in $raw_deps; do
    # Validate: dep must be in ALL_SERVICES
    if ! _in_list "$dep" "$all_services"; then
      printf '✗ Service '"'"'%s'"'"' depends on '"'"'%s'"'"' which is not registered.\n' "$svc" "$dep" >&2
      exit 1
    fi

    # Only create a graph edge if dep is also in the input set
    if _in_list "$dep" "$input_services"; then
      svc_deps[$i]="${svc_deps[$i]:+${svc_deps[$i]} }$dep"
      svc_indegree[$i]=$(( svc_indegree[i] + 1 ))
    fi
  done
done

log_debug "In-degrees: $(for (( j=0; j<total; j++ )); do printf '%s=%s ' "${svc_names[$j]}" "${svc_indegree[$j]}"; done)"

# ---------------------------------------------------------------------------
# Kahn's BFS loop
# ---------------------------------------------------------------------------

processed=0

# Build the initial zero-in-degree queue
current_queue=""
for (( i = 0; i < total; i++ )); do
  if [[ "${svc_indegree[$i]}" -eq 0 ]]; then
    current_queue="${current_queue:+$current_queue }${svc_names[$i]}"
  fi
done

while [[ -n "$current_queue" ]]; do
  # Output this layer
  echo "$current_queue"

  next_queue=""
  for svc in $current_queue; do
    processed=$(( processed + 1 ))

    # Decrement in-degree for every service that depends on $svc
    for (( j = 0; j < total; j++ )); do
      if _in_list "$svc" "${svc_deps[$j]}"; then
        svc_indegree[$j]=$(( svc_indegree[j] - 1 ))
        if [[ "${svc_indegree[$j]}" -eq 0 ]]; then
          next_queue="${next_queue:+$next_queue }${svc_names[$j]}"
        fi
      fi
    done
  done

  current_queue="$next_queue"
done

# ---------------------------------------------------------------------------
# Cycle detection — any remaining non-zero in-degree means a cycle
# ---------------------------------------------------------------------------

if [[ "$processed" -lt "$total" ]]; then
  # Find a service still stuck (in-degree > 0) to start the cycle path
  cycle_start=""
  for (( i = 0; i < total; i++ )); do
    if [[ "${svc_indegree[$i]}" -gt 0 ]]; then
      cycle_start="${svc_names[$i]}"
      break
    fi
  done

  # Walk remaining edges to reconstruct one cycle path
  cycle_path="$cycle_start"
  visited="$cycle_start"
  current="$cycle_start"

  while true; do
    idx="$(_svc_index "$current")"
    next=""

    if [[ "$idx" -ge 0 ]]; then
      for dep in ${svc_deps[$idx]}; do
        dep_idx="$(_svc_index "$dep")"
        if [[ "$dep_idx" -ge 0 ]] && [[ "${svc_indegree[$dep_idx]:-0}" -gt 0 ]]; then
          next="$dep"
          break
        fi
      done
    fi

    [[ -z "$next" ]] && break

    cycle_path="$cycle_path → $next"

    if _in_list "$next" "$visited"; then
      break
    fi

    visited="$visited $next"
    current="$next"
  done

  printf '✗ Circular dependency detected: %s\n' "$cycle_path" >&2
  exit 1
fi

log_success "Dependency layers resolved."
