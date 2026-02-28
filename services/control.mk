# ─── Control Plane Aggregates (Heimdall + Nick Fury + Mystique) ──────────────
# Provides aggregate make targets for starting/stopping/monitoring all three
# control plane services as a unit. Each service can also be managed independently
# via heimdall-*, nick-fury-*, or mystique-* targets.
#
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: control-help control-up control-down control-health control-logs

## control-help: Control plane aggregates (Heimdall + Nick Fury + Mystique)
control-help:
	@printf "\033[1mControl plane targets\033[0m\n\n"
	@grep -h "^## control-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  Run make heimdall-help / nick-fury-help / mystique-help for per-service targets.\n\n"

## control-up: Start all three control plane services (creates arc_platform_net if needed)
control-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Ensuring arc_platform_net exists...\n"
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Heimdall (Traefik)...\n"
	@$(MAKE) heimdall-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Nick Fury (OpenBao)...\n"
	@$(MAKE) nick-fury-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Mystique (Unleash)...\n"
	@$(MAKE) mystique-up --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services started\n"

## control-down: Stop all three control plane services (reverse dependency order)
control-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping control plane services...\n"
	@$(MAKE) mystique-down --no-print-directory
	@$(MAKE) nick-fury-down --no-print-directory
	@$(MAKE) heimdall-down --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services stopped\n"

## control-health: Check health of all three control plane services
control-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking control plane health...\n"
	@$(MAKE) heimdall-health --no-print-directory
	@$(MAKE) nick-fury-health --no-print-directory
	@$(MAKE) mystique-health --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All control plane services healthy\n"

## control-logs: Tail logs from all three control plane containers simultaneously
control-logs:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tailing arc-gateway, arc-vault, arc-flags logs (Ctrl-C to stop)...\n"
	@docker logs -f arc-gateway 2>&1 | sed 's/^/[heimdall]  /' & \
	 docker logs -f arc-vault   2>&1 | sed 's/^/[nick-fury] /' & \
	 docker logs -f arc-flags   2>&1 | sed 's/^/[mystique]  /' & \
	 wait
