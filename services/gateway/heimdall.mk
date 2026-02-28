# ─── Heimdall: Traefik v3 API Gateway (arc-gateway) ─────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_HEIMDALL := docker compose -f services/gateway/docker-compose.yml
HEIMDALL_IMAGE   := $(REGISTRY)/$(ORG)/arc-gateway

.PHONY: heimdall-help heimdall-build heimdall-build-fresh heimdall-push heimdall-publish heimdall-tag \
        heimdall-up heimdall-down heimdall-health heimdall-logs heimdall-clean heimdall-nuke

## heimdall-help: Traefik v3 API gateway (arc-gateway)
heimdall-help:
	@printf "\033[1mHeimdall targets\033[0m\n\n"
	@grep -h "^## heimdall-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Port 80 binding requires Docker privilege. If startup fails with\n"
	@printf "  'permission denied', change host port in a docker-compose.override.yml\n\n"

## heimdall-build: Build arc-gateway image locally using cache (fast)
heimdall-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-gateway...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(HEIMDALL_IMAGE):latest \
	  -f services/gateway/Dockerfile \
	  services/gateway/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(HEIMDALL_IMAGE):latest\n"

## heimdall-build-fresh: Build arc-gateway with --no-cache (clean rebuild)
heimdall-build-fresh: BUILD_FLAGS = --no-cache
heimdall-build-fresh: heimdall-build

## heimdall-up: Start arc-gateway (Traefik v3) in Docker
heimdall-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-gateway...\n"
	$(COMPOSE_HEIMDALL) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway started — HTTP proxy on :80, dashboard on :8090\n"

## heimdall-down: Stop arc-gateway container
heimdall-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-gateway...\n"
	$(COMPOSE_HEIMDALL) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped arc-gateway\n"

## heimdall-health: Probe arc-gateway health endpoint (:8090/ping)
heimdall-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Heimdall health (:8090)... " && \
	  if curl -sf http://localhost:8090/ping > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## heimdall-logs: Stream arc-gateway container logs
heimdall-logs:
	$(COMPOSE_HEIMDALL) logs -f

## heimdall-clean: [DESTRUCTIVE] Remove arc-gateway container
heimdall-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-gateway container.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_HEIMDALL) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway environment cleaned\n"

## heimdall-nuke: [DESTRUCTIVE] Full reset — container and local image
heimdall-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL heimdall state: container and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_HEIMDALL) down --remove-orphans
	@docker rmi $(HEIMDALL_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway reset complete — rebuild: make heimdall-build && make heimdall-up\n"

## heimdall-push: Push arc-gateway:latest to ghcr.io (requires: docker login ghcr.io)
heimdall-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(HEIMDALL_IMAGE):latest...\n"
	@docker push $(HEIMDALL_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(HEIMDALL_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## heimdall-publish: Push arc-gateway:latest to ghcr.io (visibility must be set via GitHub UI)
heimdall-publish: heimdall-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-gateway pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-gateway/settings\n"

## heimdall-tag: Tag arc-gateway:latest with a version (usage: make heimdall-tag HEIMDALL_VERSION=heimdall-v0.1.0)
heimdall-tag:
	@[ -n "$(HEIMDALL_VERSION)" ] && [ "$(HEIMDALL_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set HEIMDALL_VERSION, e.g. make heimdall-tag HEIMDALL_VERSION=heimdall-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(HEIMDALL_IMAGE):latest $(HEIMDALL_IMAGE):$(HEIMDALL_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(HEIMDALL_IMAGE):latest → $(HEIMDALL_IMAGE):$(HEIMDALL_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
