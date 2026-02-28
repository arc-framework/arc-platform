# ─── Control Plane Aggregates (Heimdall + Nick Fury + Mystique) ──────────────
# Provides aggregate make targets for starting/stopping/monitoring all three
# control plane services as a unit. Each service can also be managed independently
# via gateway-*, vault-*, or flags-* targets.
#
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: control-help control-up control-down control-health control-logs

## control-help: Control plane aggregates (Heimdall + Nick Fury + Mystique)
control-help:
	@printf "\033[1mControl plane targets\033[0m\n\n"
	@grep -h "^## control-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  Run make gateway-help / vault-help / flags-help for per-service targets.\n\n"

## control-up: Start all three control plane services (creates arc_platform_net if needed)
control-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Ensuring arc_platform_net exists...\n"
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Heimdall (Traefik)...\n"
	@$(MAKE) gateway-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Nick Fury (OpenBao)...\n"
	@$(MAKE) vault-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Mystique (Unleash)...\n"
	@$(MAKE) flags-up --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services started\n"

## control-down: Stop all three control plane services (reverse dependency order)
control-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping control plane services...\n"
	@$(MAKE) flags-down --no-print-directory
	@$(MAKE) vault-down --no-print-directory
	@$(MAKE) gateway-down --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services stopped\n"

## control-health: Check health of all three control plane services
control-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking control plane health...\n"
	@$(MAKE) gateway-health --no-print-directory
	@$(MAKE) vault-health --no-print-directory
	@$(MAKE) flags-health --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services healthy\n"

## control-logs: Tail logs from all three control plane containers simultaneously
control-logs:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tailing arc-gateway, arc-vault, arc-flags logs (Ctrl-C to stop)...\n"
	@docker logs -f arc-gateway 2>&1 | sed 's/^/[gateway] /' & \
	 docker logs -f arc-vault   2>&1 | sed 's/^/[vault]   /' & \
	 docker logs -f arc-flags   2>&1 | sed 's/^/[flags]   /' & \
	 wait
