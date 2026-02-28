# ─── Messaging Stack Aggregates (Flash + Strange + Sonic) ────────────────────
# Provides aggregate make targets for starting/stopping/monitoring all three
# messaging services as a unit. Each service can also be managed independently
# via flash-*, strange-*, or sonic-* targets.
#
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: messaging-help messaging-up messaging-down messaging-health messaging-logs

## messaging-help: Messaging stack aggregates (Flash + Strange + Sonic)
messaging-help:
	@printf "\033[1mMessaging stack targets\033[0m\n\n"
	@grep -h "^## messaging-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  Run make flash-help / strange-help / sonic-help for per-service targets.\n\n"

## messaging-up: Start all three messaging services (creates arc_platform_net if needed)
messaging-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Ensuring arc_platform_net exists...\n"
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Flash (NATS)...\n"
	@$(MAKE) flash-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Strange (Pulsar)...\n"
	@$(MAKE) strange-up --no-print-directory
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting Sonic (Redis)...\n"
	@$(MAKE) sonic-up --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All messaging services started\n"

## messaging-down: Stop all three messaging services
messaging-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping messaging services...\n"
	@$(MAKE) flash-down --no-print-directory
	@$(MAKE) strange-down --no-print-directory
	@$(MAKE) sonic-down --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All messaging services stopped\n"

## messaging-health: Check health of all three messaging services
messaging-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking messaging health...\n"
	@$(MAKE) flash-health --no-print-directory
	@$(MAKE) strange-health --no-print-directory
	@$(MAKE) sonic-health --no-print-directory
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All messaging services healthy\n"

## messaging-logs: Tail logs from all three messaging containers simultaneously
messaging-logs:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tailing arc-messaging, arc-streaming, arc-cache logs (Ctrl-C to stop)...\n"
	@docker logs -f arc-messaging  2>&1 | sed 's/^/[flash]   /' & \
	 docker logs -f arc-streaming  2>&1 | sed 's/^/[strange] /' & \
	 docker logs -f arc-cache      2>&1 | sed 's/^/[sonic]   /' & \
	 wait
