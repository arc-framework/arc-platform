# ─── Sonic: Redis Cache (arc-sonic) ───────────────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_SONIC := docker compose -f services/cache/docker-compose.yml
SONIC_IMAGE   := $(REGISTRY)/$(ORG)/arc-sonic

.PHONY: sonic-help sonic-build sonic-build-fresh sonic-up sonic-down \
        sonic-health sonic-logs sonic-clean sonic-nuke

## sonic-help: Redis cache and session store (arc-sonic)
sonic-help:
	@printf "\033[1mSonic targets\033[0m\n\n"
	@grep -h "^## sonic-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## sonic-build: Build arc-sonic image locally using cache (fast)
sonic-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-sonic...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(SONIC_IMAGE):latest \
	  -f services/cache/Dockerfile \
	  services/cache/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(SONIC_IMAGE):latest\n"

## sonic-build-fresh: Build arc-sonic with --no-cache (clean rebuild)
sonic-build-fresh: BUILD_FLAGS = --no-cache
sonic-build-fresh: sonic-build

## sonic-up: Start arc-sonic (Redis) in Docker
sonic-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-sonic...\n"
	$(COMPOSE_SONIC) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sonic started — Redis on :6379\n"

## sonic-down: Stop arc-sonic container; data volume preserved
sonic-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-sonic...\n"
	$(COMPOSE_SONIC) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use sonic-clean to remove data)\n"

## sonic-health: Probe arc-sonic via redis-cli ping
sonic-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Sonic health (redis-cli ping)... " && \
	  if docker exec arc-sonic redis-cli ping 2>/dev/null | grep -q PONG; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## sonic-logs: Stream arc-sonic container logs
sonic-logs:
	$(COMPOSE_SONIC) logs -f

## sonic-clean: [DESTRUCTIVE] Remove arc-sonic container and Redis data volume
sonic-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-sonic container + arc-sonic-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SONIC) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sonic environment cleaned\n"

## sonic-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
sonic-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL sonic state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SONIC) down --volumes --remove-orphans
	@docker rmi $(SONIC_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sonic reset complete — rebuild: make sonic-build && make sonic-up\n"
