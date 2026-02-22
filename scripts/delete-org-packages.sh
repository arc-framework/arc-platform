#!/usr/bin/env bash
SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"

# --- Allowlist: only these GitHub users may run destructive mode ---
ALLOWED_USERS=("dgtalbug")

PACKAGE_TYPE="container"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS] [ORG]

Delete all container images (ghcr.io) from a GitHub organization.

Arguments:
  ORG    GitHub organization name (default: arc-framework)

Options:
  --no-dry-run   Execute deletions (default is dry-run preview)
  --verbose      Show debug output
  --json         JSON output mode
  --no-color     Disable colors
  --help         Show this help

Safety:
  This is a DESTRUCTIVE script. To actually delete packages you need:
    1. Your GitHub username in the ALLOWED_USERS list
    2. ARC_CONFIRM_DESTRUCTIVE=1 environment variable
    3. --no-dry-run flag
    4. Type the org name when prompted

Examples:
  $0                                                # dry-run, default org
  $0 my-org                                         # dry-run, specific org
  ARC_CONFIRM_DESTRUCTIVE=1 $0 --no-dry-run my-org  # actually delete
EOF
  exit 0
}

source "$SCRIPT_DIR/lib/common.sh"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

ORG="${SCRIPT_ARGS[0]:-arc-framework}"

require_cmd "gh" "jq"
require_gh_scope "read:packages"

log_info "Org: $ORG | Type: $PACKAGE_TYPE | Dry run: $DRY_RUN"

# ---------------------------------------------------------------------------
# Fetch packages
# ---------------------------------------------------------------------------

log_info "Fetching $PACKAGE_TYPE packages..."

API_RESPONSE=$(gh api \
  --paginate \
  -H "Accept: application/vnd.github+json" \
  "/orgs/${ORG}/packages?package_type=${PACKAGE_TYPE}" 2>&1) || \
  die "API request failed: $API_RESPONSE"

# Detect error response (API returns {"message": "..."} on failure)
if echo "$API_RESPONSE" | jq -e '.message' &>/dev/null; then
  MSG=$(echo "$API_RESPONSE" | jq -r '.message')
  die "GitHub API error: $MSG"
fi

PACKAGES=$(echo "$API_RESPONSE" | jq -r '.[].name')

if [[ -z "$PACKAGES" ]]; then
  log_info "No $PACKAGE_TYPE packages found."
  exit 0
fi

PACKAGE_COUNT=$(echo "$PACKAGES" | wc -l | tr -d ' ')

log_info "📦 Found $PACKAGE_COUNT package(s):"
while read -r pkg; do
  ENCODED_PKG=$(printf '%s' "$pkg" | jq -sRr @uri)
  VERSION_COUNT=$(gh api \
    --paginate \
    -H "Accept: application/vnd.github+json" \
    "/orgs/${ORG}/packages/${PACKAGE_TYPE}/${ENCODED_PKG}/versions" \
    --jq 'length' 2>/dev/null || echo "?")
  log_info "  - $pkg ($VERSION_COUNT versions)"
done <<< "$PACKAGES"

# ---------------------------------------------------------------------------
# Dry-run gate
# ---------------------------------------------------------------------------

if is_dry_run; then
  dry_run_bail
fi

# ---------------------------------------------------------------------------
# Safety gates (destructive tier)
# ---------------------------------------------------------------------------

require_gh_scope "delete:packages"
require_allowed_user "${ALLOWED_USERS[@]}"
require_safety_pin "ARC_CONFIRM_DESTRUCTIVE"
confirm_destructive "$ORG" "org name"

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

log_warn "Deleting all $PACKAGE_COUNT package(s) from '$ORG'... 🗑️"

TOTAL_DELETED=0
TOTAL_FAILED=0

while read -r pkg; do
  ENCODED_PKG=$(printf '%s' "$pkg" | jq -sRr @uri)

  log_info "Package: $pkg"

  VERSIONS_JSON=$(gh api \
    --paginate \
    -H "Accept: application/vnd.github+json" \
    "/orgs/${ORG}/packages/${PACKAGE_TYPE}/${ENCODED_PKG}/versions" 2>/dev/null || echo "[]")

  VERSION_COUNT=$(echo "$VERSIONS_JSON" | jq 'length')

  if [[ "$VERSION_COUNT" -le 1 ]]; then
    # GitHub returns 400 if you try to delete the last tagged version via
    # the versions endpoint. Delete the package directly instead.
    log_debug "Single version — deleting package directly"
    if gh api \
      --method DELETE \
      -H "Accept: application/vnd.github+json" \
      "/orgs/${ORG}/packages/${PACKAGE_TYPE}/${ENCODED_PKG}" \
      2>/dev/null; then
      log_success "Deleted package: $pkg"
      ((TOTAL_DELETED++)) || true
    else
      log_error "Failed to delete package: $pkg"
      ((TOTAL_FAILED++)) || true
    fi
  else
    # Multiple versions: delete all but the last, then delete the package.
    VERSION_IDS=$(echo "$VERSIONS_JSON" | jq -r '.[].id')
    VERSIONS_TO_DELETE=$(echo "$VERSION_IDS" | tail -n +2)

    while read -r version_id; do
      if gh api \
        --method DELETE \
        -H "Accept: application/vnd.github+json" \
        "/orgs/${ORG}/packages/${PACKAGE_TYPE}/${ENCODED_PKG}/versions/${version_id}" \
        2>/dev/null; then
        log_debug "Deleted version $version_id"
      else
        log_debug "Skipped version $version_id (may be last tagged)"
      fi
    done <<< "$VERSIONS_TO_DELETE"

    if gh api \
      --method DELETE \
      -H "Accept: application/vnd.github+json" \
      "/orgs/${ORG}/packages/${PACKAGE_TYPE}/${ENCODED_PKG}" \
      2>/dev/null; then
      log_success "Deleted package: $pkg"
      ((TOTAL_DELETED++)) || true
    else
      log_error "Failed to delete package: $pkg"
      ((TOTAL_FAILED++)) || true
    fi
  fi
done <<< "$PACKAGES"

log_info "Complete. Deleted: $TOTAL_DELETED | Failed: $TOTAL_FAILED"
