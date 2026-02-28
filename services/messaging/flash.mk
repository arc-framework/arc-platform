# ─── Flash: NATS + JetStream Messaging (arc-flash) ───────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_FLASH := docker compose -f services/messaging/docker-compose.yml
FLASH_IMAGE   := $(REGISTRY)/$(ORG)/arc-flash

.PHONY: flash-help flash-build flash-build-fresh flash-up flash-down \
        flash-health flash-logs flash-clean flash-nuke

## flash-help: NATS + JetStream messaging broker (arc-flash)
flash-help:
	@printf "\033[1mFlash targets\033[0m\n\n"
	@grep -h "^## flash-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## flash-build: Build arc-flash image locally using cache (fast)
flash-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-flash...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(FLASH_IMAGE):latest \
	  -f services/messaging/Dockerfile \
	  services/messaging/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(FLASH_IMAGE):latest\n"

## flash-build-fresh: Build arc-flash with --no-cache (clean rebuild)
flash-build-fresh: BUILD_FLAGS = --no-cache
flash-build-fresh: flash-build

## flash-up: Start arc-flash (NATS + JetStream) in Docker
flash-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-flash...\n"
	$(COMPOSE_FLASH) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flash started — NATS on :4222, monitor on :8222\n"

## flash-down: Stop arc-flash container; data volume preserved
flash-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-flash...\n"
	$(COMPOSE_FLASH) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use flash-clean to remove data)\n"

## flash-health: Probe arc-flash health endpoint (:8222/healthz)
flash-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Flash health (:8222)... " && \
	  if curl -sf http://localhost:8222/healthz > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## flash-logs: Stream arc-flash container logs
flash-logs:
	$(COMPOSE_FLASH) logs -f

## flash-clean: [DESTRUCTIVE] Remove arc-flash container and JetStream data volume
flash-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-flash container + arc-flash-jetstream volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLASH) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flash environment cleaned\n"

## flash-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
flash-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL flash state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLASH) down --volumes --remove-orphans
	@docker rmi $(FLASH_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flash reset complete — rebuild: make flash-build && make flash-up\n"
