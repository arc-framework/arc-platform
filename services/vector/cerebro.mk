# ─── Cerebro: Qdrant Vector Database (arc-vector-db) ────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_CEREBRO := docker compose -f services/vector/docker-compose.yml
CEREBRO_IMAGE   := $(REGISTRY)/$(ORG)/arc-vector-db

.PHONY: cerebro-help cerebro-build cerebro-build-fresh cerebro-push cerebro-publish cerebro-tag \
        cerebro-up cerebro-down cerebro-health cerebro-logs cerebro-clean cerebro-nuke

## cerebro-help: Qdrant vector database (arc-vector-db)
cerebro-help:
	@printf "\033[1mCerebro targets\033[0m\n\n"
	@grep -h "^## cerebro-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## cerebro-build: Build arc-vector-db image locally using cache (fast)
cerebro-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-vector-db...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(CEREBRO_IMAGE):latest \
	  -f services/vector/Dockerfile \
	  services/vector/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(CEREBRO_IMAGE):latest\n"

## cerebro-build-fresh: Build arc-vector-db with --no-cache (clean rebuild)
cerebro-build-fresh: BUILD_FLAGS = --no-cache
cerebro-build-fresh: cerebro-build

## cerebro-up: Start arc-vector-db (Qdrant) in Docker
cerebro-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-vector-db...\n"
	$(COMPOSE_CEREBRO) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db started — REST on :6333, gRPC on :6334\n"

## cerebro-down: Stop arc-vector-db container; data volume preserved
cerebro-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-vector-db...\n"
	$(COMPOSE_CEREBRO) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use cerebro-clean to remove data)\n"

## cerebro-health: Probe arc-vector-db health (/readyz :6333)
cerebro-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Cerebro health (:6333)... " && \
	  if curl -sf http://localhost:6333/readyz > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## cerebro-logs: Stream arc-vector-db container logs
cerebro-logs:
	$(COMPOSE_CEREBRO) logs -f

## cerebro-clean: [DESTRUCTIVE] Remove arc-vector-db container and data volume
cerebro-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-vector-db container + arc-vector-db-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_CEREBRO) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db environment cleaned\n"

## cerebro-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
cerebro-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL cerebro state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_CEREBRO) down --volumes --remove-orphans
	@docker rmi $(CEREBRO_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db reset complete — rebuild: make cerebro-build && make cerebro-up\n"

## cerebro-push: Push arc-vector-db:latest to ghcr.io (requires: docker login ghcr.io)
cerebro-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(CEREBRO_IMAGE):latest...\n"
	@docker push $(CEREBRO_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(CEREBRO_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## cerebro-publish: Push arc-vector-db:latest to ghcr.io (visibility must be set via GitHub UI)
cerebro-publish: cerebro-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-vector-db/settings\n"

## cerebro-tag: Tag arc-vector-db:latest with a version (usage: make cerebro-tag CEREBRO_VERSION=data-v0.1.0)
cerebro-tag:
	@[ -n "$(CEREBRO_VERSION)" ] && [ "$(CEREBRO_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set CEREBRO_VERSION, e.g. make cerebro-tag CEREBRO_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(CEREBRO_IMAGE):latest $(CEREBRO_IMAGE):$(CEREBRO_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(CEREBRO_IMAGE):latest → $(CEREBRO_IMAGE):$(CEREBRO_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
