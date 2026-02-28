# ─── Flash: NATS + JetStream Messaging (arc-messaging) ───────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_FLASH := docker compose -f services/messaging/docker-compose.yml
FLASH_IMAGE   := $(REGISTRY)/$(ORG)/arc-messaging

.PHONY: flash-help flash-build flash-build-fresh flash-push flash-publish flash-tag \
        flash-health flash-logs flash-clean flash-nuke

## flash-help: NATS + JetStream messaging broker (arc-messaging)
flash-help:
	@printf "\033[1mFlash targets\033[0m\n\n"
	@grep -h "^## flash-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## flash-build: Build arc-messaging image locally using cache (fast)
flash-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-messaging...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(FLASH_IMAGE):latest \
	  -f services/messaging/Dockerfile \
	  services/messaging/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(FLASH_IMAGE):latest\n"

## flash-build-fresh: Build arc-messaging with --no-cache (clean rebuild)
flash-build-fresh: BUILD_FLAGS = --no-cache
flash-build-fresh: flash-build

## flash-up: Start arc-messaging (NATS + JetStream) in Docker
flash-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-messaging...\n"
	$(COMPOSE_FLASH) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging started — NATS on :4222, monitor on :8222\n"

## flash-down: Stop arc-messaging container; data volume preserved
flash-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-messaging...\n"
	$(COMPOSE_FLASH) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use flash-clean to remove data)\n"

## flash-health: Probe arc-messaging health endpoint (:8222/healthz)
flash-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Flash health (:8222)... " && \
	  if curl -sf http://localhost:8222/healthz > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## flash-logs: Stream arc-messaging container logs
flash-logs:
	$(COMPOSE_FLASH) logs -f

## flash-clean: [DESTRUCTIVE] Remove arc-messaging container and JetStream data volume
flash-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-messaging container + arc-messaging-jetstream volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLASH) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging environment cleaned\n"

## flash-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
flash-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL flash state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLASH) down --volumes --remove-orphans
	@docker rmi $(FLASH_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging reset complete — rebuild: make flash-build && make flash-up\n"
## flash-push: Push arc-messaging:latest to ghcr.io (requires: docker login ghcr.io)
flash-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(FLASH_IMAGE):latest...\n"
	@docker push $(FLASH_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(FLASH_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## flash-publish: Push arc-messaging:latest to ghcr.io (visibility must be set via GitHub UI)
flash-publish: flash-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-messaging/settings\n"

## flash-tag: Tag arc-messaging:latest with a version (usage: make flash-tag FLASH_VERSION=flash-v0.1.0)
flash-tag:
	@[ -n "$(FLASH_VERSION)" ] && [ "$(FLASH_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set FLASH_VERSION, e.g. make flash-tag FLASH_VERSION=flash-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(FLASH_IMAGE):latest $(FLASH_IMAGE):$(FLASH_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(FLASH_IMAGE):latest → $(FLASH_IMAGE):$(FLASH_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
