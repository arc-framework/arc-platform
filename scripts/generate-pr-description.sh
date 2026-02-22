#!/usr/bin/env bash
SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARC_SCRIPT_ARGS="$*"

usage() {
  cat <<EOF
Usage: $0 [OPTIONS] [BASE_BRANCH]

Generate a PR description from branch changes and SpecKit spec files.

Arguments:
  BASE_BRANCH    Branch to compare against (default: main)

Options:
  --no-dry-run   N/A (this script is read-only)
  --verbose      Show debug output
  --json         Output PR description as JSON
  --no-color     Disable colors
  --help         Show this help

Examples:
  $0                    # compare against main
  $0 develop            # compare against develop
EOF
  exit 0
}

source "$SCRIPT_DIR/lib/common.sh"

require_cmd "git" "sed" "awk"

# ---------------------------------------------------------------------------
# Gather context
# ---------------------------------------------------------------------------

COMPARE_BRANCH="${SCRIPT_ARGS[0]:-main}"

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ -z "$CURRENT_BRANCH" ]]; then
  die "Not on a git branch."
fi

log_info "Branch: $CURRENT_BRANCH"
log_info "Comparing against: $COMPARE_BRANCH"

# Validate compare branch exists
if ! git rev-parse --verify "$COMPARE_BRANCH" >/dev/null 2>&1; then
  log_warn "$COMPARE_BRANCH not found, trying 'develop'..."
  COMPARE_BRANCH="develop"
  if ! git rev-parse --verify "$COMPARE_BRANCH" >/dev/null 2>&1; then
    die "Neither 'main' nor 'develop' branch found."
  fi
fi

# Extract feature ID from branch name (e.g., 003-feature-name -> 003)
FEATURE_ID=$(echo "$CURRENT_BRANCH" | grep -oE '^[0-9]+' || echo "")
if [[ -z "$FEATURE_ID" ]]; then
  log_debug "Branch doesn't follow NNN-feature-name convention."
  FEATURE_ID=""
fi

# ---------------------------------------------------------------------------
# Find spec directory
# ---------------------------------------------------------------------------

SPEC_DIR=""
if [[ -n "$FEATURE_ID" ]]; then
  # Try exact branch name first, then prefix match
  if [[ -d "specs/${CURRENT_BRANCH}" ]]; then
    SPEC_DIR="specs/${CURRENT_BRANCH}"
  else
    SPEC_DIR=$(find specs -maxdepth 1 -type d -name "${FEATURE_ID}-*" 2>/dev/null | head -n 1)
  fi
fi

if [[ -n "$SPEC_DIR" ]]; then
  log_success "Spec directory: $SPEC_DIR"
else
  log_debug "No spec directory found."
fi

SPEC_NAME=$(basename "${SPEC_DIR:-$CURRENT_BRANCH}")

# ---------------------------------------------------------------------------
# Analyze changes
# ---------------------------------------------------------------------------

log_info "Analyzing changes..."

SHORTSTAT=$(git diff "$COMPARE_BRANCH" --shortstat 2>/dev/null || echo "")
FILES_CHANGED=$(echo "$SHORTSTAT" | awk '{print $1+0}')
INSERTIONS=$(echo "$SHORTSTAT" | grep -oE '[0-9]+ insertion' | awk '{print $1}' || echo "0")
DELETIONS=$(echo "$SHORTSTAT" | grep -oE '[0-9]+ deletion' | awk '{print $1}' || echo "0")

: "${FILES_CHANGED:=0}" "${INSERTIONS:=0}" "${DELETIONS:=0}"

# Count file types from diff
count_type() { git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -c "$1" 2>/dev/null || echo "0"; }

DOCKERFILE_CHANGES=$(count_type "Dockerfile")
COMPOSE_CHANGES=$(count_type "docker-compose\|compose\.yml")
SCRIPT_CHANGES=$(count_type '\.sh$')
DOC_CHANGES=$(count_type '\.md$')
YAML_CHANGES=$(count_type '\.ya\?ml$')
GO_CHANGES=$(count_type '\.go$')
PY_CHANGES=$(count_type '\.py$')

log_debug "Files: $FILES_CHANGED | +$INSERTIONS -$DELETIONS"
log_debug "Docker: $DOCKERFILE_CHANGES | Compose: $COMPOSE_CHANGES | Go: $GO_CHANGES | Py: $PY_CHANGES"

# Detect affected areas in the monorepo
CHANGED_AREAS=""
if git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -q '^cli/'; then
  CHANGED_AREAS="${CHANGED_AREAS}cli "
fi
if git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -q '^services/'; then
  CHANGED_AREAS="${CHANGED_AREAS}services "
fi
if git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -q '^sdk/'; then
  CHANGED_AREAS="${CHANGED_AREAS}sdk "
fi
if git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -q '^docs/'; then
  CHANGED_AREAS="${CHANGED_AREAS}docs "
fi
if git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -q '^scripts/'; then
  CHANGED_AREAS="${CHANGED_AREAS}scripts "
fi

# Detect affected services
CHANGED_SERVICES=$(git diff "$COMPARE_BRANCH" --name-only 2>/dev/null \
  | grep '^services/' \
  | cut -d'/' -f2 \
  | sort -u \
  | tr '\n' ' ' || echo "")

# ---------------------------------------------------------------------------
# Read spec context
# ---------------------------------------------------------------------------

SPEC_DESCRIPTION=""
COMPLETED_TASKS="0"
TOTAL_TASKS="0"
TOTAL_PHASES="0"

if [[ -n "$SPEC_DIR" ]]; then
  SPEC_FILE="$SPEC_DIR/spec.md"
  TASKS_FILE="$SPEC_DIR/tasks.md"

  if [[ -f "$SPEC_FILE" ]]; then
    # Extract summary or overview
    SPEC_DESCRIPTION=$(sed -n '/^## Summary$/,/^## /p' "$SPEC_FILE" 2>/dev/null | tail -n +2 | sed '$d' | sed '/^$/d' | head -n 5)
    if [[ -z "$SPEC_DESCRIPTION" ]]; then
      SPEC_DESCRIPTION=$(sed -n '/^## Overview$/,/^## /p' "$SPEC_FILE" 2>/dev/null | tail -n +2 | sed '$d' | sed '/^$/d' | head -n 5)
    fi
  fi

  if [[ -f "$TASKS_FILE" ]]; then
    TOTAL_PHASES=$(grep -c '^## Phase\|^## \[Phase' "$TASKS_FILE" 2>/dev/null || echo "0")
    COMPLETED_TASKS=$(grep -c '^\- \[[Xx]\]' "$TASKS_FILE" 2>/dev/null || echo "0")
    TOTAL_TASKS=$(grep -c '^\- \[' "$TASKS_FILE" 2>/dev/null || echo "0")
  fi
fi

# ---------------------------------------------------------------------------
# Auto-detect change type checkboxes
# ---------------------------------------------------------------------------

check() { [[ "$1" != "0" ]] && echo "[x]" || echo "[ ]"; }

DOCKER_CHECK=$(check "$DOCKERFILE_CHANGES")
INFRA_CHECK="[ ]"
[[ "$COMPOSE_CHANGES" != "0" || "$YAML_CHANGES" != "0" ]] && INFRA_CHECK="[x]"
DOC_CHECK=$(check "$DOC_CHANGES")
GO_CHECK=$(check "$GO_CHANGES")
PY_CHECK=$(check "$PY_CHANGES")
SCRIPT_CHECK=$(check "$SCRIPT_CHANGES")

# Detect security-related changes
SECURITY_CHECK="[ ]"
SECURITY_FILES=$(git diff "$COMPARE_BRANCH" --name-only 2>/dev/null | grep -ciE "security|secret|auth|kratos" || echo "0")
[[ "$SECURITY_FILES" != "0" ]] && SECURITY_CHECK="[x]"

# ---------------------------------------------------------------------------
# Generate PR description
# ---------------------------------------------------------------------------

if [[ -n "$SPEC_DIR" ]]; then
  PR_FILE="$SPEC_DIR/pr-description.md"
else
  PR_FILE="pr-description.md"
fi

log_info "Generating: $PR_FILE"

cat > "$PR_FILE" << PREOF
## Description

$(if [[ -n "$SPEC_DESCRIPTION" ]]; then
  echo "$SPEC_DESCRIPTION"
elif [[ -n "$FEATURE_ID" ]]; then
  echo "Implements feature #$FEATURE_ID: \`$SPEC_NAME\`"
else
  echo "Changes for branch: \`$CURRENT_BRANCH\`"
fi)

## Type of Change

- $DOCKER_CHECK 🐳 Docker/Container changes
- $INFRA_CHECK 🔧 Infrastructure configuration
- $GO_CHECK 🔩 Go (CLI / SDK / infra)
- $PY_CHECK 🧠 Python (AI / ML / services)
- $SCRIPT_CHECK 📜 Scripts / Makefile
- $SECURITY_CHECK 🔒 Security
- $DOC_CHECK 📚 Documentation
- [ ] 💥 Breaking change
- [ ] 🐛 Bug fix

## Monorepo Impact

| Area | Affected |
|------|----------|
| \`cli/\` | $(if echo "$CHANGED_AREAS" | grep -q 'cli'; then echo "✓"; else echo "—"; fi) |
| \`services/\` | $(if echo "$CHANGED_AREAS" | grep -q 'services'; then echo "✓ ${CHANGED_SERVICES}"; else echo "—"; fi) |
| \`sdk/\` | $(if echo "$CHANGED_AREAS" | grep -q 'sdk'; then echo "✓"; else echo "—"; fi) |
| \`docs/\` | $(if echo "$CHANGED_AREAS" | grep -q 'docs'; then echo "✓"; else echo "—"; fi) |
| \`scripts/\` | $(if echo "$CHANGED_AREAS" | grep -q 'scripts'; then echo "✓"; else echo "—"; fi) |

$(if [[ -n "$FEATURE_ID" ]]; then
cat << ISSUE
## Related Issue

Relates to feature #$FEATURE_ID — \`$SPEC_NAME\`
ISSUE
fi)

## Changes

### Summary

| Metric | Value |
|--------|-------|
| Files Changed | $FILES_CHANGED |
| Insertions | +$INSERTIONS |
| Deletions | -$DELETIONS |
$(if [[ "$TOTAL_TASKS" != "0" ]]; then echo "| Tasks | $COMPLETED_TASKS / $TOTAL_TASKS |"; fi)
$(if [[ "$TOTAL_PHASES" != "0" ]]; then echo "| Phases | $TOTAL_PHASES |"; fi)

### By Category

| Category | Count |
|----------|-------|
| Dockerfiles | $DOCKERFILE_CHANGES |
| Compose / YAML | $COMPOSE_CHANGES / $YAML_CHANGES |
| Go files | $GO_CHANGES |
| Python files | $PY_CHANGES |
| Shell scripts | $SCRIPT_CHANGES |
| Documentation | $DOC_CHANGES |

$(if [[ -n "$SPEC_DIR" ]] && [[ -f "$SPEC_DIR/tasks.md" ]]; then
  echo "### Completed Phases"
  echo ""
  grep -E '^## Phase|^## \[Phase' "$SPEC_DIR/tasks.md" 2>/dev/null | head -n 10 | while read -r line; do
    phase_name="${line#\#\# }"
    echo "- **$phase_name**"
  done
  echo ""
fi)

## Testing

- [ ] \`make -C cli build && make -C cli test\` passes
- [ ] \`make -C scripts check\` passes (shellcheck + syntax)
- [ ] Docker builds complete (\`make otel-build\`)
- [ ] Health checks pass (\`make otel-health\`)
- [ ] Documentation is accurate

## Checklist

- [ ] Code follows project conventions (see \`CLAUDE.md\`)
- [ ] No secrets or credentials committed
- [ ] Destructive scripts have safety gates
- [ ] Error messages include remediation steps
- [ ] Added to relevant catalog / README

---

**Branch**: \`$CURRENT_BRANCH\` → \`$COMPARE_BRANCH\`
$(if [[ -n "$SPEC_DIR" ]]; then echo "**Spec**: \`$SPEC_DIR\`"; fi)
**Generated**: $(date '+%Y-%m-%d %H:%M:%S')
PREOF

log_success "PR description generated: $PR_FILE"
log_info ""
log_info "📊 $FILES_CHANGED files changed (+$INSERTIONS/-$DELETIONS)"
[[ -n "$CHANGED_AREAS" ]] && log_info "📦 Areas: $CHANGED_AREAS"
[[ -n "$CHANGED_SERVICES" ]] && log_info "🔧 Services: $CHANGED_SERVICES"
log_info ""
log_info "Next steps:"
log_info "  1. Review: $PR_FILE"
log_info "  2. Create PR: gh pr create --body-file $PR_FILE"
