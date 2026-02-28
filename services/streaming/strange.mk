# ─── Strange: Apache Pulsar Streaming (arc-strange) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_STRANGE := docker compose -f services/streaming/docker-compose.yml
STRANGE_IMAGE   := $(REGISTRY)/$(ORG)/arc-strange

.PHONY: strange-help strange-build strange-build-fresh strange-up strange-down \
        strange-health strange-logs strange-clean strange-nuke

## strange-help: Apache Pulsar streaming broker (arc-strange)
strange-help:
	@printf "\033[1mStrange targets\033[0m\n\n"
	@grep -h "^## strange-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## strange-build: Build arc-strange image locally using cache (fast)
strange-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-strange...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(STRANGE_IMAGE):latest \
	  -f services/streaming/Dockerfile \
	  services/streaming/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(STRANGE_IMAGE):latest\n"

## strange-build-fresh: Build arc-strange with --no-cache (clean rebuild)
strange-build-fresh: BUILD_FLAGS = --no-cache
strange-build-fresh: strange-build

## strange-up: Start arc-strange (Pulsar standalone) — waits up to 120s for readiness
strange-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-strange...\n"
	$(COMPOSE_STRANGE) up -d
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Waiting for arc-strange to become ready (cold start: ~90s)..."
	@i=0; until curl -sf http://localhost:8082/admin/v2/brokers/health > /dev/null 2>&1; do \
	  printf "."; sleep 5; i=$$((i+1)); \
	  if [ $$i -ge 24 ]; then \
	    printf "\n$(COLOR_ERR)✗ arc-strange did not become healthy after 120s$(COLOR_OFF)\n"; \
	    printf "  Check logs: make strange-logs\n"; \
	    exit 1; \
	  fi; \
	done
	@printf "\n$(COLOR_OK)✓$(COLOR_OFF) arc-strange is ready — broker on :6650, admin on :8082\n"

## strange-down: Stop arc-strange container; data volume preserved
strange-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-strange...\n"
	$(COMPOSE_STRANGE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use strange-clean to remove data)\n"

## strange-health: Probe arc-strange health endpoint (:8082/admin/v2/brokers/health)
strange-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Strange health (:8082)... " && \
	  if curl -sf http://localhost:8082/admin/v2/brokers/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## strange-logs: Stream arc-strange container logs
strange-logs:
	$(COMPOSE_STRANGE) logs -f

## strange-clean: [DESTRUCTIVE] Remove arc-strange container and Pulsar data volume
strange-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-strange container + arc-strange-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STRANGE) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-strange environment cleaned\n"

## strange-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
strange-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL strange state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STRANGE) down --volumes --remove-orphans
	@docker rmi $(STRANGE_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-strange reset complete — rebuild: make strange-build && make strange-up\n"
