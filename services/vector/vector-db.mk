# ─── Cerebro: Qdrant Vector Database (arc-vector-db) ────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_VECTOR_DB := docker compose -f services/vector/docker-compose.yml
VECTOR_DB_IMAGE   := $(REGISTRY)/$(ORG)/arc-vector-db

.PHONY: vector-db-help vector-db-build vector-db-build-fresh vector-db-push vector-db-publish vector-db-tag \
        vector-db-up vector-db-down vector-db-health vector-db-logs vector-db-clean vector-db-nuke

## vector-db-help: Qdrant vector database (arc-vector-db)
vector-db-help:
	@printf "\033[1mCerebro targets\033[0m\n\n"
	@grep -h "^## vector-db-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## vector-db-build: Build arc-vector-db image locally using cache (fast)
vector-db-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-vector-db...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(VECTOR_DB_IMAGE):latest \
	  -f services/vector/Dockerfile \
	  services/vector/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(VECTOR_DB_IMAGE):latest\n"

## vector-db-build-fresh: Build arc-vector-db with --no-cache (clean rebuild)
vector-db-build-fresh: BUILD_FLAGS = --no-cache
vector-db-build-fresh: vector-db-build

## vector-db-up: Start arc-vector-db (Qdrant) in Docker
vector-db-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-vector-db...\n"
	$(COMPOSE_VECTOR_DB) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db started — REST on :6333, gRPC on :6334\n"

## vector-db-down: Stop arc-vector-db container; data volume preserved
vector-db-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-vector-db...\n"
	$(COMPOSE_VECTOR_DB) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use vector-db-clean to remove data)\n"

## vector-db-health: Probe arc-vector-db health (/readyz :6333)
vector-db-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Cerebro health (:6333)... " && \
	  if curl -sf http://localhost:6333/readyz > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## vector-db-logs: Stream arc-vector-db container logs
vector-db-logs:
	$(COMPOSE_VECTOR_DB) logs -f

## vector-db-clean: [DESTRUCTIVE] Remove arc-vector-db container and data volume
vector-db-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-vector-db container + arc-vector-db-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_VECTOR_DB) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db environment cleaned\n"

## vector-db-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
vector-db-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL cerebro state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_VECTOR_DB) down --volumes --remove-orphans
	@docker rmi $(VECTOR_DB_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db reset complete — rebuild: make vector-db-build && make vector-db-up\n"

## vector-db-push: Push arc-vector-db:latest to ghcr.io (requires: docker login ghcr.io)
vector-db-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(VECTOR_DB_IMAGE):latest...\n"
	@docker push $(VECTOR_DB_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(VECTOR_DB_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## vector-db-publish: Push arc-vector-db:latest to ghcr.io (visibility must be set via GitHub UI)
vector-db-publish: vector-db-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vector-db pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-vector-db/settings\n"

## vector-db-tag: Tag arc-vector-db:latest with a version (usage: make vector-db-tag VECTOR_DB_VERSION=data-v0.1.0)
vector-db-tag:
	@[ -n "$(VECTOR_DB_VERSION)" ] && [ "$(VECTOR_DB_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set VECTOR_DB_VERSION, e.g. make vector-db-tag VECTOR_DB_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(VECTOR_DB_IMAGE):latest $(VECTOR_DB_IMAGE):$(VECTOR_DB_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(VECTOR_DB_IMAGE):latest → $(VECTOR_DB_IMAGE):$(VECTOR_DB_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
