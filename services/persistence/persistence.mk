# ─── Oracle: PostgreSQL 17 Persistence (arc-persistence) ─────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_SQL_DB := docker compose -f services/persistence/docker-compose.yml
SQL_DB_IMAGE   := $(REGISTRY)/$(ORG)/arc-persistence

.PHONY: persistence-help persistence-build persistence-build-fresh persistence-push persistence-publish persistence-tag \
        persistence-up persistence-down persistence-health persistence-logs persistence-clean persistence-nuke

## persistence-help: PostgreSQL 17 persistence (arc-persistence)
persistence-help:
	@printf "\033[1mOracle targets\033[0m\n\n"
	@grep -h "^## persistence-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: POSTGRES_PASSWORD is ignored after data dir is initialized.\n"
	@printf "  To reset credentials: make persistence-nuke && make persistence-up\n\n"

## persistence-build: Build arc-persistence image locally using cache (fast)
persistence-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-persistence...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(SQL_DB_IMAGE):latest \
	  -f services/persistence/Dockerfile \
	  services/persistence/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(SQL_DB_IMAGE):latest\n"

## persistence-build-fresh: Build arc-persistence with --no-cache (clean rebuild)
persistence-build-fresh: BUILD_FLAGS = --no-cache
persistence-build-fresh: persistence-build

## persistence-up: Start arc-persistence (PostgreSQL 17) in Docker
persistence-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-persistence...\n"
	$(COMPOSE_SQL_DB) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-persistence started — PostgreSQL on :5432\n"

## persistence-down: Stop arc-persistence container; data volume preserved
persistence-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-persistence...\n"
	$(COMPOSE_SQL_DB) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use persistence-clean to remove data)\n"

## persistence-health: Probe arc-persistence health (pg_isready :5432)
persistence-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Oracle health (:5432)... " && \
	  if docker exec arc-persistence pg_isready -U arc > /dev/null 2>&1; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## persistence-logs: Stream arc-persistence container logs
persistence-logs:
	$(COMPOSE_SQL_DB) logs -f

## persistence-clean: [DESTRUCTIVE] Remove arc-persistence container and data volume
persistence-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-persistence container + arc-persistence-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SQL_DB) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-persistence environment cleaned\n"

## persistence-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
persistence-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL persistence state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SQL_DB) down --volumes --remove-orphans
	@docker rmi $(SQL_DB_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-persistence reset complete — rebuild: make persistence-build && make persistence-up\n"

## persistence-push: Push arc-persistence:latest to ghcr.io (requires: docker login ghcr.io)
persistence-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(SQL_DB_IMAGE):latest...\n"
	@docker push $(SQL_DB_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(SQL_DB_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## persistence-publish: Push arc-persistence:latest to ghcr.io (visibility must be set via GitHub UI)
persistence-publish: persistence-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-persistence pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-persistence/settings\n"

## persistence-tag: Tag arc-persistence:latest with a version (usage: make persistence-tag PERSISTENCE_VERSION=data-v0.1.0)
persistence-tag:
	@[ -n "$(PERSISTENCE_VERSION)" ] && [ "$(PERSISTENCE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set PERSISTENCE_VERSION, e.g. make persistence-tag PERSISTENCE_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(SQL_DB_IMAGE):latest $(SQL_DB_IMAGE):$(PERSISTENCE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(SQL_DB_IMAGE):latest → $(SQL_DB_IMAGE):$(PERSISTENCE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
