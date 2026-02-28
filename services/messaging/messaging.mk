# ─── Flash: NATS + JetStream Messaging (arc-messaging) ───────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_MESSAGING := docker compose -f services/messaging/docker-compose.yml
MESSAGING_IMAGE   := $(REGISTRY)/$(ORG)/arc-messaging

.PHONY: messaging-help messaging-build messaging-build-fresh messaging-push messaging-publish messaging-tag \
        messaging-health messaging-logs messaging-clean messaging-nuke

## messaging-help: NATS + JetStream messaging broker (arc-messaging)
messaging-help:
	@printf "\033[1mFlash targets\033[0m\n\n"
	@grep -h "^## messaging-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## messaging-build: Build arc-messaging image locally using cache (fast)
messaging-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-messaging...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(MESSAGING_IMAGE):latest \
	  -f services/messaging/Dockerfile \
	  services/messaging/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(MESSAGING_IMAGE):latest\n"

## messaging-build-fresh: Build arc-messaging with --no-cache (clean rebuild)
messaging-build-fresh: BUILD_FLAGS = --no-cache
messaging-build-fresh: messaging-build

## messaging-up: Start arc-messaging (NATS + JetStream) in Docker
messaging-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-messaging...\n"
	$(COMPOSE_MESSAGING) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging started — NATS on :4222, monitor on :8222\n"

## messaging-down: Stop arc-messaging container; data volume preserved
messaging-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-messaging...\n"
	$(COMPOSE_MESSAGING) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use messaging-clean to remove data)\n"

## messaging-health: Probe arc-messaging health endpoint (:8222/healthz)
messaging-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Flash health (:8222)... " && \
	  if curl -sf http://localhost:8222/healthz > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## messaging-logs: Stream arc-messaging container logs
messaging-logs:
	$(COMPOSE_MESSAGING) logs -f

## messaging-clean: [DESTRUCTIVE] Remove arc-messaging container and JetStream data volume
messaging-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-messaging container + arc-messaging-jetstream volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_MESSAGING) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging environment cleaned\n"

## messaging-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
messaging-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL flash state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_MESSAGING) down --volumes --remove-orphans
	@docker rmi $(MESSAGING_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging reset complete — rebuild: make messaging-build && make messaging-up\n"
## messaging-push: Push arc-messaging:latest to ghcr.io (requires: docker login ghcr.io)
messaging-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(MESSAGING_IMAGE):latest...\n"
	@docker push $(MESSAGING_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(MESSAGING_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## messaging-publish: Push arc-messaging:latest to ghcr.io (visibility must be set via GitHub UI)
messaging-publish: messaging-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-messaging pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-messaging/settings\n"

## messaging-tag: Tag arc-messaging:latest with a version (usage: make messaging-tag MESSAGING_VERSION=messaging-v0.1.0)
messaging-tag:
	@[ -n "$(MESSAGING_VERSION)" ] && [ "$(MESSAGING_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set MESSAGING_VERSION, e.g. make messaging-tag MESSAGING_VERSION=messaging-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(MESSAGING_IMAGE):latest $(MESSAGING_IMAGE):$(MESSAGING_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(MESSAGING_IMAGE):latest → $(MESSAGING_IMAGE):$(MESSAGING_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
