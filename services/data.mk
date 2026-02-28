# ─── Data Layer Aggregates (Oracle + Cerebro + Tardis) ───────────────────────
# Provides aggregate make targets for starting/stopping/monitoring all three
# data services as a unit. Each service can also be managed independently
# via oracle-*, cerebro-*, or tardis-* targets.
#
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: data-help data-up data-down data-health data-logs

## data-help: Data layer aggregates (Oracle + Cerebro + Tardis)
data-help:
	@printf "\033[1mData layer targets\033[0m\n\n"
	@grep -h "^## data-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  Run make oracle-help / cerebro-help / tardis-help for per-service targets.\n\n"

## data-up: Start all three data services (creates arc_platform_net if needed)
data-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Ensuring arc_platform_net exists...\n"
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Oracle (PostgreSQL)...\n"
	@$(MAKE) oracle-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Cerebro (Qdrant)...\n"
	@$(MAKE) cerebro-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Tardis (MinIO)...\n"
	@$(MAKE) tardis-up --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All data services started\n"

## data-down: Stop all three data services
data-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping data services...\n"
	@$(MAKE) oracle-down --no-print-directory
	@$(MAKE) cerebro-down --no-print-directory
	@$(MAKE) tardis-down --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All data services stopped\n"

## data-health: Check health of all three data services
data-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking data layer health...\n"
	@$(MAKE) oracle-health --no-print-directory
	@$(MAKE) cerebro-health --no-print-directory
	@$(MAKE) tardis-health --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All data services healthy\n"

## data-logs: Tail logs from all three data containers simultaneously
data-logs:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tailing arc-sql-db, arc-vector-db, arc-storage logs (Ctrl-C to stop)...\n"
	@docker logs -f arc-sql-db    2>&1 | sed 's/^/[oracle]  /' & \
	 docker logs -f arc-vector-db 2>&1 | sed 's/^/[cerebro] /' & \
	 docker logs -f arc-storage   2>&1 | sed 's/^/[tardis]  /' & \
	 wait
