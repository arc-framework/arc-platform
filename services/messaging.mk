# ─── Transport Layer Aggregates (Messaging + Streaming + Cache) ────────────────
# Provides aggregate make targets for starting/stopping/monitoring all three
# transport services as a unit. Each service can also be managed independently
# via messaging-*, streaming-*, or cache-* targets.
#
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: transport-help transport-up transport-down transport-health transport-logs

## transport-help: Transport layer aggregates (Messaging + Streaming + Cache)
transport-help:
	@printf "\033[1mTransport layer targets\033[0m\n\n"
	@grep -h "^## transport-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  Run make messaging-help / streaming-help / cache-help for per-service targets.\n\n"

## transport-up: Start all three transport services (creates arc_platform_net if needed)
transport-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Ensuring arc_platform_net exists...\n"
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Flash (NATS)...\n"
	@$(MAKE) messaging-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Strange (Pulsar)...\n"
	@$(MAKE) streaming-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Sonic (Redis)...\n"
	@$(MAKE) cache-up --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All transport services started\n"

## transport-down: Stop all three transport services
transport-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping transport services...\n"
	@$(MAKE) messaging-down --no-print-directory
	@$(MAKE) streaming-down --no-print-directory
	@$(MAKE) cache-down --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All transport services stopped\n"

## transport-health: Check health of all three transport services
transport-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking transport health...\n"
	@$(MAKE) messaging-health --no-print-directory
	@$(MAKE) streaming-health --no-print-directory
	@$(MAKE) cache-health --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All transport services healthy\n"

## transport-logs: Tail logs from all three transport containers simultaneously
transport-logs:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tailing arc-messaging, arc-streaming, arc-cache logs (Ctrl-C to stop)...\n"
	@docker logs -f arc-messaging  2>&1 | sed 's/^/[messaging]  /' & \
	 docker logs -f arc-streaming  2>&1 | sed 's/^/[streaming]  /' & \
	 docker logs -f arc-cache      2>&1 | sed 's/^/[cache]      /' & \
	 wait
