# ─── Heimdall: Traefik v3 API Gateway (arc-gateway) ─────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_GATEWAY := docker compose -f services/gateway/docker-compose.yml
GATEWAY_IMAGE   := $(REGISTRY)/$(ORG)/arc-gateway

.PHONY: gateway-help gateway-build gateway-build-fresh gateway-push gateway-publish gateway-tag \
        gateway-up gateway-down gateway-health gateway-logs gateway-clean gateway-nuke

## gateway-help: Traefik v3 API gateway (arc-gateway)
gateway-help:
	@printf "\033[1mHeimdall targets\033[0m\n\n"
	@grep -h "^## gateway-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Port 80 binding requires Docker privilege. If startup fails with\n"
	@printf "  'permission denied', change host port in a docker-compose.override.yml\n\n"

## gateway-build: Build arc-gateway image locally using cache (fast)
gateway-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-gateway...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(GATEWAY_IMAGE):latest \
	  -f services/gateway/Dockerfile \
	  services/gateway/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(GATEWAY_IMAGE):latest\n"

## gateway-build-fresh: Build arc-gateway with --no-cache (clean rebuild)
gateway-build-fresh: BUILD_FLAGS = --no-cache
gateway-build-fresh: gateway-build

## gateway-up: Start arc-gateway (Traefik v3) in Docker
gateway-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-gateway...\n"
	$(COMPOSE_GATEWAY) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway started — HTTP proxy on :80, dashboard on :8090\n"

## gateway-down: Stop arc-gateway container
gateway-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-gateway...\n"
	$(COMPOSE_GATEWAY) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped arc-gateway\n"

## gateway-health: Probe arc-gateway health endpoint (:8090/ping)
gateway-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Heimdall health (:8090)... " && \
	  if curl -sf http://localhost:8090/ping > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## gateway-logs: Stream arc-gateway container logs
gateway-logs:
	$(COMPOSE_GATEWAY) logs -f

## gateway-clean: [DESTRUCTIVE] Remove arc-gateway container
gateway-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-gateway container.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_GATEWAY) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway environment cleaned\n"

## gateway-nuke: [DESTRUCTIVE] Full reset — container and local image
gateway-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL heimdall state: container and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_GATEWAY) down --remove-orphans
	@docker rmi $(GATEWAY_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway reset complete — rebuild: make gateway-build && make gateway-up\n"

## gateway-push: Push arc-gateway:latest to ghcr.io (requires: docker login ghcr.io)
gateway-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(GATEWAY_IMAGE):latest...\n"
	@docker push $(GATEWAY_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(GATEWAY_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## gateway-publish: Push arc-gateway:latest to ghcr.io (visibility must be set via GitHub UI)
gateway-publish: gateway-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-gateway/settings\n"

## gateway-tag: Tag arc-gateway:latest with a version (usage: make gateway-tag GATEWAY_VERSION=gateway-v0.1.0)
gateway-tag:
	@[ -n "$(GATEWAY_VERSION)" ] && [ "$(GATEWAY_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set GATEWAY_VERSION, e.g. make gateway-tag GATEWAY_VERSION=gateway-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(GATEWAY_IMAGE):latest $(GATEWAY_IMAGE):$(GATEWAY_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(GATEWAY_IMAGE):latest → $(GATEWAY_IMAGE):$(GATEWAY_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
