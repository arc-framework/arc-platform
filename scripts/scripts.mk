# ─── Scripts ──────────────────────────────────────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# Running from repo root fixes working-directory issues that occur with make -C.
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTS_DIR_PATH := scripts

# Branch to compare against for PR description (override: make scripts-pr BASE=develop)
BASE ?= main

.PHONY: scripts-help scripts-pr scripts-pr-json \
        scripts-check scripts-check-syntax scripts-check-lint \
        scripts-packages-list scripts-packages-list-json scripts-packages-delete \
        scripts-permissions publish-all

## scripts-help: Utility scripts (PR description, package management, validation)
scripts-help:
	@printf "\033[1mScripts targets\033[0m\n\n"
	@grep -h "^## scripts-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## scripts-pr: Generate PR description from branch changes (writes to specs/<feature>/pr-description.md)
scripts-pr:
	@$(SCRIPTS_DIR_PATH)/generate-pr-description.sh $(BASE)

## scripts-pr-json: Generate PR description as JSON
scripts-pr-json:
	@$(SCRIPTS_DIR_PATH)/generate-pr-description.sh --json $(BASE)

## scripts-check: Run all script validations (syntax + shellcheck)
scripts-check: scripts-check-syntax scripts-check-lint

## scripts-check-syntax: Verify bash syntax for all scripts
scripts-check-syntax:
	@echo "Checking bash syntax..."
	@fail=0; \
	for f in $(SCRIPTS_DIR_PATH)/*.sh $(SCRIPTS_DIR_PATH)/lib/*.sh; do \
	  if bash -n "$$f" 2>/dev/null; then \
	    echo "  ✓ $$(basename $$f)"; \
	  else \
	    echo "  ✗ $$(basename $$f)"; fail=1; \
	  fi; \
	done; \
	[ $$fail -eq 0 ] && echo "✓ All files OK" || exit 1

## scripts-check-lint: Run shellcheck (skips if not installed: brew install shellcheck)
scripts-check-lint:
	@if command -v shellcheck >/dev/null 2>&1; then \
	  shellcheck -x $(SCRIPTS_DIR_PATH)/*.sh $(SCRIPTS_DIR_PATH)/lib/*.sh \
	    && printf "$(COLOR_OK)✓$(COLOR_OFF) shellcheck passed\n" \
	    || { printf "$(COLOR_ERR)✗$(COLOR_OFF) shellcheck found issues\n"; exit 1; }; \
	else \
	  printf "$(COLOR_WARN)!$(COLOR_OFF) shellcheck not installed — skipping\n"; \
	fi

## scripts-packages-list: Preview GHCR packages for arc-framework org (dry-run)
scripts-packages-list:
	@$(SCRIPTS_DIR_PATH)/delete-org-packages.sh $(ORG)

## scripts-packages-list-json: Preview packages in JSON-lines format
scripts-packages-list-json:
	@$(SCRIPTS_DIR_PATH)/delete-org-packages.sh --json $(ORG)

## scripts-packages-delete: [DESTRUCTIVE] Delete all GHCR container packages
scripts-packages-delete:
	@ARC_CONFIRM_DESTRUCTIVE=1 $(SCRIPTS_DIR_PATH)/delete-org-packages.sh --no-dry-run $(ORG)

## scripts-permissions: Ensure all scripts are executable
scripts-permissions:
	@chmod +x $(SCRIPTS_DIR_PATH)/*.sh $(SCRIPTS_DIR_PATH)/lib/*.sh
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All scripts are executable\n"

## publish-all: Build and push all platform images to ghcr.io (requires: docker login ghcr.io + gh auth)
publish-all:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building and publishing all A.R.C. platform images...\n"
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Requires: docker login ghcr.io   and   gh auth login\n"
	$(MAKE) sql-db-build      sql-db-publish      --no-print-directory
	$(MAKE) vector-db-build   vector-db-publish   --no-print-directory
	$(MAKE) storage-build     storage-publish     --no-print-directory
	$(MAKE) gateway-build     gateway-publish     --no-print-directory
	$(MAKE) vault-build       vault-publish       --no-print-directory
	$(MAKE) flags-build       flags-publish       --no-print-directory
	$(MAKE) cache-build       cache-publish       --no-print-directory
	$(MAKE) messaging-build   messaging-publish   --no-print-directory
	$(MAKE) streaming-build   streaming-publish   --no-print-directory
	$(MAKE) cortex-build      cortex-publish      --no-print-directory
	$(MAKE) otel-build        otel-publish        --no-print-directory
	$(MAKE) realtime-build         realtime-publish         --no-print-directory
	$(MAKE) realtime-ingress-build realtime-ingress-publish --no-print-directory
	$(MAKE) realtime-egress-build  realtime-egress-publish  --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All images published to ghcr.io/arc-framework\n"
