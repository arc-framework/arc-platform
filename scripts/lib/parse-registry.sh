#!/usr/bin/env bash
# scripts/lib/parse-registry.sh — Scan services/**/service.yaml into Make variable assignments.
#
# Usage (from repo root):
#   scripts/lib/parse-registry.sh > .make/registry.mk
#
# Stdout: Make variable assignments (pure, suitable for direct redirection).
# Stderr: Log messages via common.sh helpers.
#
# Requires: awk, find (POSIX), bash 3.2+
# No external deps (no yq, jq, python).

set -euo pipefail

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SERVICES_DIR="${SERVICES_DIR:-services}"
DEFAULT_TIMEOUT=120

# ---------------------------------------------------------------------------
# Validate input
# ---------------------------------------------------------------------------

if [[ ! -d "$SERVICES_DIR" ]]; then
  die "services directory not found at '$SERVICES_DIR'. Run from repo root."
fi

log_info "Scanning $SERVICES_DIR for service.yaml files"

# ---------------------------------------------------------------------------
# Phase 1: Parse each service.yaml with awk.
#
# YAML shapes we handle per file:
#
#   codename: <name>
#   health: <endpoint>        ← single-line value, may contain spaces
#   timeout: <seconds>        ← optional integer
#   depends_on: []            ← inline empty list → no deps
#   depends_on:               ← block list follows
#     - dep-a
#     - dep-b                 ← may have inline comments: "- dep # comment"
#
# Output per file (to stdout, one line per field, tab-separated):
#   codename<TAB><codename>
#   health<TAB><endpoint>
#   timeout<TAB><value>
#   dep<TAB><depname>         ← one line per dependency
#   dir<TAB><directory>
# ---------------------------------------------------------------------------

_parse_one() {
  local yaml_file="$1"
  local dir
  dir="$(dirname "$yaml_file")"

  awk -v dir="$dir" '
  function ltrim(s) { sub(/^[[:space:]]+/, "", s); return s }
  function rtrim(s) { sub(/[[:space:]]+$/, "", s); return s }
  function trim(s)  { return rtrim(ltrim(s)) }

  BEGIN {
    codename = ""
    image    = ""
    health   = ""
    timeout  = ""
    in_deps  = 0
  }

  # Skip blank lines and comment-only lines
  /^[[:space:]]*#/  { next }
  /^[[:space:]]*$/  { next }

  # image: <value>
  /^[[:space:]]*image:[[:space:]]/ {
    val = $0
    sub(/^[[:space:]]*image:[[:space:]]*/, "", val)
    sub(/[[:space:]]+#.*$/, "", val)
    image = trim(val)
    in_deps = 0
    next
  }

  # codename: <value>
  /^[[:space:]]*codename:[[:space:]]/ {
    val = $0
    sub(/^[[:space:]]*codename:[[:space:]]*/, "", val)
    # strip inline comment
    sub(/#.*$/, "", val)
    codename = trim(val)
    in_deps = 0
    next
  }

  # health: <value>  (value may contain spaces — grab everything after "health: ")
  /^[[:space:]]*health:[[:space:]]/ {
    val = $0
    sub(/^[[:space:]]*health:[[:space:]]*/, "", val)
    # strip inline comment only if it starts with " #" (avoid stripping URL fragments)
    sub(/[[:space:]]+#.*$/, "", val)
    health = trim(val)
    in_deps = 0
    next
  }

  # timeout: <value>
  /^[[:space:]]*timeout:[[:space:]]/ {
    val = $0
    sub(/^[[:space:]]*timeout:[[:space:]]*/, "", val)
    sub(/#.*$/, "", val)
    timeout = trim(val)
    in_deps = 0
    next
  }

  # depends_on: []   ← inline empty list
  /^[[:space:]]*depends_on:[[:space:]]*\[\]/ {
    in_deps = 0
    next
  }

  # depends_on:   ← block list starts on next lines
  /^[[:space:]]*depends_on:[[:space:]]*$/ {
    in_deps = 1
    next
  }

  # List item under depends_on block:  "  - depname  # optional comment"
  in_deps && /^[[:space:]]*-[[:space:]]/ {
    val = $0
    sub(/^[[:space:]]*-[[:space:]]*/, "", val)
    # strip inline comment
    sub(/[[:space:]]+#.*$/, "", val)
    dep = trim(val)
    if (dep != "") {
      print "dep\t" dep
    }
    next
  }

  # Any non-indented (or differently-indented) key resets depends_on mode
  /^[[:space:]]*[a-zA-Z_]/ {
    in_deps = 0
  }

  END {
    if (codename != "") {
      print "codename\t" codename
      print "image\t"    image
      print "health\t"   health
      print "timeout\t"  timeout
      print "dir\t"      dir
    }
  }
  ' "$yaml_file"
}

# ---------------------------------------------------------------------------
# Phase 2: Collect all parsed data, then emit Make variables.
# ---------------------------------------------------------------------------

# Temporary storage: use parallel indexed arrays via numbered lines.
# We accumulate results in awk-friendly temp strings and pass to a final awk.

all_codenames=""

# We'll accumulate everything into a flat record stream for the final emitter.
# Format: CODENAME<TAB>FIELD<TAB>VALUE
# This lets a single final awk pass emit the Make assignments in order.

tmpdata=""

while IFS= read -r yaml_file; do
  log_debug "Parsing $yaml_file"

  # Parse this file into field=value lines
  file_data="$(_parse_one "$yaml_file")"

  # Extract codename from the parsed data (it's the last line printed by awk END)
  codename=""
  while IFS=$'\t' read -r field value; do
    if [[ "$field" == "codename" ]]; then
      codename="$value"
    fi
  done <<EOF
$file_data
EOF

  if [[ -z "$codename" ]]; then
    log_warn "No codename found in $yaml_file — skipping"
    continue
  fi

  # Append codename to ordered list
  all_codenames="${all_codenames:+$all_codenames }$codename"

  # Append tagged records: CODENAME<TAB>FIELD<TAB>VALUE
  while IFS=$'\t' read -r field value; do
    tmpdata="${tmpdata}${codename}	${field}	${value}
"
  done <<EOF
$file_data
EOF

done < <(find "$SERVICES_DIR" -name "service.yaml" | sort)

if [[ -z "$all_codenames" ]]; then
  log_warn "No service.yaml files found under $SERVICES_DIR"
fi

log_info "Found services: $all_codenames"

# ---------------------------------------------------------------------------
# Phase 3: Emit Make variable assignments via awk.
#
# Input format (tmpdata): CODENAME<TAB>FIELD<TAB>VALUE, one record per line.
# We also pass the ordered codename list and default timeout as awk vars.
# ---------------------------------------------------------------------------

awk -v all_codenames="$all_codenames" \
    -v default_timeout="$DEFAULT_TIMEOUT" \
'
function make_varname(s,    v) {
  v = s
  gsub(/-/, "_", v)
  return v
}

# Parse all records into associative arrays keyed by codename
{
  codename = $1
  field    = $2
  # value is everything after the second tab (may contain tabs, though unlikely)
  value = ""
  n = split($0, parts, "\t")
  for (i = 3; i <= n; i++) {
    value = (i == 3) ? parts[i] : value "\t" parts[i]
  }

  if (field == "codename") {
    svc_image[codename]    = (codename in svc_image)    ? svc_image[codename]    : ""
    svc_health[codename]   = (codename in svc_health)   ? svc_health[codename]   : ""
    svc_timeout[codename]  = (codename in svc_timeout)  ? svc_timeout[codename]  : ""
    svc_dir[codename]      = (codename in svc_dir)      ? svc_dir[codename]      : ""
    svc_deps[codename]     = (codename in svc_deps)     ? svc_deps[codename]     : ""
  } else if (field == "image") {
    svc_image[codename] = value
  } else if (field == "health") {
    svc_health[codename] = value
  } else if (field == "timeout") {
    svc_timeout[codename] = value
  } else if (field == "dir") {
    svc_dir[codename] = value
  } else if (field == "dep") {
    svc_deps[codename] = (svc_deps[codename] == "") ? value : svc_deps[codename] " " value
  }
}

END {
  # Header
  print "# Generated by scripts/lib/parse-registry.sh \342\200\224 do not edit manually"
  print "# Source: services/**/service.yaml"
  print ""
  print "ALL_SERVICES := " all_codenames

  # Per-service variables — iterate in declared order via all_codenames
  n = split(all_codenames, ordered, " ")
  for (i = 1; i <= n; i++) {
    cn = ordered[i]
    vn = make_varname(cn)

    to = svc_timeout[cn]
    if (to == "") to = default_timeout

    print ""
    print "SERVICE_" vn "_IMAGE := "   svc_image[cn]
    print "SERVICE_" vn "_HEALTH := "  svc_health[cn]
    print "SERVICE_" vn "_DEPENDS := " svc_deps[cn]
    print "SERVICE_" vn "_TIMEOUT := " to
    print "SERVICE_" vn "_DIR := "     svc_dir[cn]
  }
}
' <<EOF
$tmpdata
EOF

log_success "registry.mk generated from $SERVICES_DIR/**/service.yaml"
