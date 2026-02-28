# ─── Strange: Apache Pulsar Streaming (arc-streaming) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_STREAMING := docker compose -f services/streaming/docker-compose.yml
STREAMING_IMAGE   := $(REGISTRY)/$(ORG)/arc-streaming

.PHONY: streaming-help streaming-build streaming-build-fresh streaming-push streaming-publish streaming-tag \
        streaming-health streaming-logs streaming-clean streaming-nuke

## streaming-help: Apache Pulsar streaming broker (arc-streaming)
streaming-help:
	@printf "\033[1mStrange targets\033[0m\n\n"
	@grep -h "^## streaming-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## streaming-build: Build arc-streaming image locally using cache (fast)
streaming-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-streaming...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(STREAMING_IMAGE):latest \
	  -f services/streaming/Dockerfile \
	  services/streaming/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(STREAMING_IMAGE):latest\n"

## streaming-build-fresh: Build arc-streaming with --no-cache (clean rebuild)
streaming-build-fresh: BUILD_FLAGS = --no-cache
streaming-build-fresh: streaming-build

## streaming-up: Start arc-streaming (Pulsar standalone) — waits up to 120s for readiness
streaming-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-streaming...\n"
	$(COMPOSE_STREAMING) up -d
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Waiting for arc-streaming to become ready (cold start: ~90s)..."
	@i=0; until curl -sf http://localhost:8082/admin/v2/brokers/health > /dev/null 2>&1; do \
	  printf "."; sleep 5; i=$$((i+1)); \
	  if [ $$i -ge 24 ]; then \
	    printf "\n$(COLOR_ERR)✗ arc-streaming did not become healthy after 120s$(COLOR_OFF)\n"; \
	    printf "  Check logs: make streaming-logs\n"; \
	    exit 1; \
	  fi; \
	done
	@printf "\n$(COLOR_OK)✓$(COLOR_OFF) arc-streaming is ready — broker on :6650, admin on :8082\n"

## streaming-down: Stop arc-streaming container; data volume preserved
streaming-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-streaming...\n"
	$(COMPOSE_STREAMING) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use streaming-clean to remove data)\n"

## streaming-health: Probe arc-streaming health endpoint (:8082/admin/v2/brokers/health)
streaming-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Strange health (:8082)... " && \
	  if curl -sf http://localhost:8082/admin/v2/brokers/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## streaming-logs: Stream arc-streaming container logs
streaming-logs:
	$(COMPOSE_STREAMING) logs -f

## streaming-clean: [DESTRUCTIVE] Remove arc-streaming container and Pulsar data volume
streaming-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-streaming container + arc-streaming-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STREAMING) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-streaming environment cleaned\n"

## streaming-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
streaming-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL strange state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STREAMING) down --volumes --remove-orphans
	@docker rmi $(STREAMING_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-streaming reset complete — rebuild: make streaming-build && make streaming-up\n"
## streaming-push: Push arc-streaming:latest to ghcr.io (requires: docker login ghcr.io)
streaming-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(STREAMING_IMAGE):latest...\n"
	@docker push $(STREAMING_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(STREAMING_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## streaming-publish: Push arc-streaming:latest to ghcr.io (visibility must be set via GitHub UI)
streaming-publish: streaming-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-streaming pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-streaming/settings\n"

## streaming-tag: Tag arc-streaming:latest with a version (usage: make streaming-tag STREAMING_VERSION=streaming-v0.1.0)
streaming-tag:
	@[ -n "$(STREAMING_VERSION)" ] && [ "$(STREAMING_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set STREAMING_VERSION, e.g. make streaming-tag STREAMING_VERSION=streaming-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(STREAMING_IMAGE):latest $(STREAMING_IMAGE):$(STREAMING_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(STREAMING_IMAGE):latest → $(STREAMING_IMAGE):$(STREAMING_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
