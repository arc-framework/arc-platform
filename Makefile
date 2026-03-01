# ─── A.R.C. Platform — Root Makefile ─────────────────────────────────────────
# Single entrypoint for all service orchestration.
# All paths are relative to the repo root — no cd commands used.
#
# Usage:
#   make help         List available services and their help commands
#   make otel-help    List all OTEL stack targets
#   make otel-up      Start the OTEL observability stack
# ─────────────────────────────────────────────────────────────────────────────

# ─── Logging ──────────────────────────────────────────────────────────────────
# Shared ANSI colour vars — available in all included .mk fragments.
# Symbols: → (step)   ✓ (success)   ! (warning/destructive)   ✗ (error)
COLOR_INFO := \033[0;34m
COLOR_OK   := \033[0;32m
COLOR_WARN := \033[0;33m
COLOR_ERR  := \033[0;31m
COLOR_OFF  := \033[0m

# ─── Profile ──────────────────────────────────────────────────────────────────
# Default profile for make dev. Override: make dev PROFILE=reason
PROFILE ?= think

# ─── Services ─────────────────────────────────────────────────────────────────
# Add one include per service as the platform grows.
include services/otel/otel.mk
include services/cortex/cortex.mk
include services/messaging/messaging.mk
include services/streaming/streaming.mk
include services/cache/cache.mk
include services/messaging.mk
include services/persistence/sql-db.mk
include services/vector/vector-db.mk
include services/storage/storage.mk
include services/data.mk
include services/gateway/gateway.mk
include services/secrets/vault.mk
include services/flags/flags.mk
include services/control.mk
include services/realtime/realtime.mk
include services/reasoner/reasoner.mk

# ─── Generated orchestration metadata (.make/ — gitignored) ───────────────────
# -include silently skips missing files on first run; generation rules create them.
-include .make/profiles.mk
-include .make/registry.mk

.make:
	@mkdir -p $@

# Regenerate profiles.mk when profiles.yaml changes
.make/profiles.mk: services/profiles.yaml | .make
	@scripts/lib/parse-profiles.sh > $@
	@printf "$(COLOR_OK)✓$(COLOR_OFF) .make/profiles.mk regenerated\n"

# Regenerate registry.mk when any service.yaml changes
_REGISTRY_DEPS := $(shell find services -name service.yaml 2>/dev/null)
.make/registry.mk: $(_REGISTRY_DEPS) | .make
	@scripts/lib/parse-registry.sh > $@
	@printf "$(COLOR_OK)✓$(COLOR_OFF) .make/registry.mk regenerated\n"

## dev-regen: Force-rebuild .make/ generated files
dev-regen:
	@rm -f .make/profiles.mk .make/registry.mk
	@$(MAKE) .make/profiles.mk .make/registry.mk --no-print-directory

# ─── Utilities ────────────────────────────────────────────────────────────────
include scripts/scripts.mk

# ─── Help ─────────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help
.PHONY: help

## help: Show available targets and service help commands
help:
	@printf "\033[1mA.R.C. Platform\033[0m\n\n"
	@printf "  \033[1mDev orchestration\033[0m (PROFILE=think by default):\n"
	@grep -h "^## dev" $(MAKEFILE_LIST) \
	  | sed 's/^## \([^:]*\): \(.*\)/    make \1    \2/'
	@printf "\n  \033[1mServices\033[0m:\n"
	@grep -h "^## .*-help:" $(MAKEFILE_LIST) \
	  | sed 's/^## \(.*\)-help: \(.*\)/    make \1-help    \2/' \
	  | sort
	@printf "\n  \033[1mScripts & publishing\033[0m:\n"
	@grep -h "^## scripts-\|^## publish-" $(MAKEFILE_LIST) \
	  | sed 's/^## \([^:]*\): \(.*\)/    make \1    \2/' \
	  | sort
	@printf "\n  Run \033[1mmake <service>-help\033[0m for the full service target list.\n\n"

# ─── Dev orchestration ────────────────────────────────────────────────────────
# Usage:
#   make dev                  Start think profile (default)
#   make dev PROFILE=reason   Start reason profile (includes full OTEL)
#   make dev-down             Stop all profile services
#   make dev-health           Check health of all profile services
#   make dev-logs             Tail logs from all profile services
#   make dev-status           Show container status table
#   make dev-prereqs          Check developer environment only
#   make dev-images           Check/pull required images for $(PROFILE) profile
#   make dev-clean            [DESTRUCTIVE] Remove containers + volumes + orphans
#   make dev-nuke             [DESTRUCTIVE] Remove containers + volumes + images + orphans
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: dev dev-up dev-down dev-wait dev-health dev-logs dev-status \
        dev-clean dev-nuke dev-prereqs dev-networks dev-regen dev-images

## dev: Start all services in $(PROFILE) profile in dependency order
dev: dev-prereqs dev-networks .make/profiles.mk .make/registry.mk dev-images dev-up dev-wait
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Profile '$(PROFILE)' is ready\n"

dev-prereqs:
	@scripts/lib/check-dev-prereqs.sh

## dev-images: Check/pull required images for $(PROFILE) profile (local first, then registry)
dev-images: .make/profiles.mk .make/registry.mk
	@scripts/lib/check-images.sh $$(scripts/lib/profile-services.sh $(PROFILE))

dev-networks:
	@docker network create arc_platform_net 2>/dev/null || true
	@docker network create arc_otel_net     2>/dev/null || true

dev-up: .make/profiles.mk .make/registry.mk
	@services=$$(scripts/lib/profile-services.sh $(PROFILE)) || exit 1; \
	 printf "$(COLOR_INFO)→$(COLOR_OFF) Resolving startup order for profile '$(PROFILE)'...\n"; \
	 layers=$$(scripts/lib/resolve-deps.sh $$services 2>/dev/null); \
	 layer_num=0; \
	 echo "$$layers" | while IFS= read -r layer; do \
	   layer_num=$$((layer_num+1)); \
	   printf "$(COLOR_INFO)→$(COLOR_OFF) Layer $$layer_num: $$layer\n"; \
	   for svc in $$layer; do \
	     $(MAKE) $${svc}-up --no-print-directory; \
	   done; \
	 done

dev-wait: .make/profiles.mk .make/registry.mk
	@for svc in $$(scripts/lib/profile-services.sh $(PROFILE)); do \
	   varname="$$(echo $$svc | tr '-' '_')"; \
	   health="$$(grep "^SERVICE_$${varname}_HEALTH" .make/registry.mk | sed 's/.*:=[[:space:]]*//')"; \
	   timeout="$$(grep "^SERVICE_$${varname}_TIMEOUT" .make/registry.mk | sed 's/.*:=[[:space:]]*//')"; \
	   [ -z "$$timeout" ] && timeout=120; \
	   scripts/lib/wait-for-health.sh "$$svc" "$$health" "$$timeout"; \
	 done

## dev-down: Stop all services in $(PROFILE) profile
dev-down: .make/profiles.mk .make/registry.mk
	@for svc in $$(scripts/lib/profile-services.sh $(PROFILE)); do \
	   $(MAKE) $${svc}-down --no-print-directory 2>/dev/null || true; \
	 done; \
	 printf "$(COLOR_OK)✓$(COLOR_OFF) Profile '$(PROFILE)' stopped\n"

## dev-health: Check health of all services in $(PROFILE) profile
dev-health: .make/profiles.mk .make/registry.mk
	@failed=0; \
	 for svc in $$(scripts/lib/profile-services.sh $(PROFILE)); do \
	   $(MAKE) $${svc}-health --no-print-directory 2>/dev/null || failed=$$((failed+1)); \
	 done; \
	 [ "$$failed" -eq 0 ] \
	   && printf "$(COLOR_OK)✓$(COLOR_OFF) All services healthy\n" \
	   || { printf "$(COLOR_ERR)✗$(COLOR_OFF) $$failed service(s) unhealthy\n"; exit 1; }

## dev-logs: Tail logs from all services in $(PROFILE) profile
dev-logs: .make/profiles.mk .make/registry.mk
	@for svc in $$(scripts/lib/profile-services.sh $(PROFILE)); do \
	   $(MAKE) $${svc}-logs --no-print-directory 2>/dev/null & \
	 done; \
	 wait

## dev-status: Show container status for all services in $(PROFILE) profile
dev-status: .make/profiles.mk .make/registry.mk
	@printf "%-20s %-10s %s\n" "SERVICE" "STATUS" "HEALTH"; \
	 printf "%-20s %-10s %s\n" "-------" "------" "------"; \
	 for svc in $$(scripts/lib/profile-services.sh $(PROFILE)); do \
	   status="$$(docker ps --filter name=arc-$$svc --format '{{.Status}}' 2>/dev/null | head -1)"; \
	   [ -z "$$status" ] && status="stopped"; \
	   varname="$$(echo $$svc | tr '-' '_')"; \
	   health="$$(grep "^SERVICE_$${varname}_HEALTH" .make/registry.mk | sed 's/.*:=[[:space:]]*//')"; \
	   if scripts/lib/wait-for-health.sh "$$svc" "$$health" 1 2>/dev/null; then \
	     hmark="$(COLOR_OK)✓$(COLOR_OFF)"; \
	   else \
	     hmark="$(COLOR_ERR)✗$(COLOR_OFF)"; \
	   fi; \
	   printf "%-20s %-10s %b\n" "$$svc" "$$status" "$$hmark"; \
	 done

## dev-clean: [DESTRUCTIVE] Remove containers + volumes + orphans for $(PROFILE) profile
dev-clean: .make/profiles.mk .make/registry.mk
	@scripts/lib/dev-clean.sh $(PROFILE)

## dev-nuke: [DESTRUCTIVE] Remove containers + volumes + images + orphans for $(PROFILE) profile
dev-nuke: .make/profiles.mk .make/registry.mk
	@scripts/lib/dev-nuke.sh $(PROFILE)
