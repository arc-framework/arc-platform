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

# ─── Services ─────────────────────────────────────────────────────────────────
# Add one include per service as the platform grows.
include services/otel/otel.mk
# future: include services/gateway/gateway.mk
# future: include services/persistence/persistence.mk

# ─── Help ─────────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help
.PHONY: help

## help: Show available services and their help commands
help:
	@printf "\033[1mA.R.C. Platform\033[0m\n\n"
	@printf "  Services:\n"
	@grep -h "^## .*-help:" $(MAKEFILE_LIST) \
	  | sed 's/^## \(.*\)-help: \(.*\)/    make \1-help    \2/' \
	  | sort
	@printf "\n  Run \033[1mmake <service>-help\033[0m for the full target list.\n\n"
