# ─── Sonic: Redis Cache (arc-cache) ───────────────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_CACHE := docker compose -f services/cache/docker-compose.yml
CACHE_IMAGE   := $(REGISTRY)/$(ORG)/arc-cache

.PHONY: cache-help cache-build cache-build-fresh cache-push cache-publish cache-tag \
        cache-health cache-logs cache-clean cache-nuke

## cache-help: Redis cache and session store (arc-cache)
cache-help:
	@printf "\033[1mSonic targets\033[0m\n\n"
	@grep -h "^## cache-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## cache-build: Build arc-cache image locally using cache (fast)
cache-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-cache...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(CACHE_IMAGE):latest \
	  -f services/cache/Dockerfile \
	  services/cache/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(CACHE_IMAGE):latest\n"

## cache-build-fresh: Build arc-cache with --no-cache (clean rebuild)
cache-build-fresh: BUILD_FLAGS = --no-cache
cache-build-fresh: cache-build

## cache-up: Start arc-cache (Redis) in Docker
cache-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-cache...\n"
	$(COMPOSE_CACHE) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cache started — Redis on :6379\n"

## cache-down: Stop arc-cache container; data volume preserved
cache-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-cache...\n"
	$(COMPOSE_CACHE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use cache-clean to remove data)\n"

## cache-health: Probe arc-cache via redis-cli ping
cache-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Sonic health (redis-cli ping)... " && \
	  if docker exec arc-cache redis-cli ping 2>/dev/null | grep -q PONG; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## cache-logs: Stream arc-cache container logs
cache-logs:
	$(COMPOSE_CACHE) logs -f

## cache-clean: [DESTRUCTIVE] Remove arc-cache container and Redis data volume
cache-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-cache container + arc-cache-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_CACHE) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cache environment cleaned\n"

## cache-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
cache-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL cache state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_CACHE) down --volumes --remove-orphans
	@docker rmi $(CACHE_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cache reset complete — rebuild: make cache-build && make cache-up\n"
## cache-push: Push arc-cache:latest to ghcr.io (requires: docker login ghcr.io)
cache-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(CACHE_IMAGE):latest...\n"
	@docker push $(CACHE_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(CACHE_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## cache-publish: Push arc-cache:latest to ghcr.io (visibility must be set via GitHub UI)
cache-publish: cache-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cache pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-cache/settings\n"

## cache-tag: Tag arc-cache:latest with a version (usage: make cache-tag CACHE_VERSION=cache-v0.1.0)
cache-tag:
	@[ -n "$(CACHE_VERSION)" ] && [ "$(CACHE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set CACHE_VERSION, e.g. make cache-tag CACHE_VERSION=cache-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(CACHE_IMAGE):latest $(CACHE_IMAGE):$(CACHE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(CACHE_IMAGE):latest → $(CACHE_IMAGE):$(CACHE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
