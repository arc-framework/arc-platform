# ─── A.R.C. Scripts — Makefile ────────────────────────────────────────────────
# Runner and validation for scripts/ utilities.
# All targets use common.sh conventions (dry-run default, structured logging).
#
# Usage:
#   make help               Show available targets
#   make packages-list      Preview packages (dry-run)
#   make check              Syntax + shellcheck validation
#   make packages-delete ORG=my-org
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTS_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

ORG ?= arc-framework

.PHONY: help \
        packages-list packages-list-json packages-delete \
        check check-syntax check-lint \
        list permissions

# ─── Help ─────────────────────────────────────────────────────────────────────

## help: Show available targets
help:
	@echo ""
	@echo "  📦 scripts/Makefile — A.R.C. script runner"
	@echo ""
	@grep -E '^## [a-z].*:' $(MAKEFILE_LIST) | sed 's/## /  /'
	@echo ""

# ─── Packages ────────────────────────────────────────────────────────────────

## packages-list: 📋 Preview container packages for an org (dry-run)
packages-list:
	@$(SCRIPTS_DIR)/delete-org-packages.sh $(ORG)

## packages-list-json: 📋 Preview packages in JSON-lines format
packages-list-json:
	@$(SCRIPTS_DIR)/delete-org-packages.sh --json $(ORG)

## packages-delete: 🗑️  Delete all container packages (requires safety gates)
## Override: make packages-delete ORG=my-org
packages-delete:
	@ARC_CONFIRM_DESTRUCTIVE=1 $(SCRIPTS_DIR)/delete-org-packages.sh --no-dry-run $(ORG)

# ─── Validation ──────────────────────────────────────────────────────────────

## check: 🔍 Run all validations (syntax + shellcheck)
check: check-syntax check-lint

## check-syntax: 🔍 Verify bash syntax for all scripts
check-syntax:
	@echo "Checking bash syntax..."
	@fail=0; \
	for f in $(SCRIPTS_DIR)/*.sh $(SCRIPTS_DIR)/lib/*.sh; do \
		if bash -n "$$f" 2>/dev/null; then \
			echo "  ✓ $$(basename $$f)"; \
		else \
			echo "  ✗ $$(basename $$f)"; fail=1; \
		fi; \
	done; \
	[ $$fail -eq 0 ] && echo "✓ All files OK" || exit 1

## check-lint: 🔍 Run shellcheck (skips if not installed)
check-lint:
	@if command -v shellcheck >/dev/null 2>&1; then \
		echo "Running shellcheck..."; \
		shellcheck -x $(SCRIPTS_DIR)/*.sh $(SCRIPTS_DIR)/lib/*.sh \
			&& echo "✓ shellcheck passed" \
			|| { echo "✗ shellcheck found issues"; exit 1; }; \
	else \
		echo "⚠ shellcheck not installed — skipping (brew install shellcheck)"; \
	fi

# ─── Utilities ───────────────────────────────────────────────────────────────

## list: 📄 Show all scripts with descriptions
list:
	@echo ""
	@echo "  Available scripts:"
	@echo ""
	@for f in $(SCRIPTS_DIR)/*.sh; do \
		name=$$(basename "$$f"); \
		desc=$$($$f --help 2>/dev/null | sed -n '3p' | sed 's/^ *//' || echo "(no description)"); \
		printf '    %-30s %s\n' "$$name" "$$desc"; \
	done
	@echo ""

## permissions: 🔧 Ensure all scripts are executable
permissions:
	@chmod +x $(SCRIPTS_DIR)/*.sh $(SCRIPTS_DIR)/lib/*.sh
	@echo "✓ All scripts are executable"
