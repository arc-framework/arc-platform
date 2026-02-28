# ─── Oracle: PostgreSQL 17 Persistence (arc-sql-db) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_SQL_DB := docker compose -f services/persistence/docker-compose.yml
SQL_DB_IMAGE   := $(REGISTRY)/$(ORG)/arc-sql-db

.PHONY: sql-db-help sql-db-build sql-db-build-fresh sql-db-push sql-db-publish sql-db-tag \
        sql-db-up sql-db-down sql-db-health sql-db-logs sql-db-clean sql-db-nuke

## sql-db-help: PostgreSQL 17 persistence (arc-sql-db)
sql-db-help:
	@printf "\033[1mOracle targets\033[0m\n\n"
	@grep -h "^## sql-db-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: POSTGRES_PASSWORD is ignored after data dir is initialized.\n"
	@printf "  To reset credentials: make sql-db-nuke && make sql-db-up\n\n"

## sql-db-build: Build arc-sql-db image locally using cache (fast)
sql-db-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-sql-db...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(SQL_DB_IMAGE):latest \
	  -f services/persistence/Dockerfile \
	  services/persistence/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(SQL_DB_IMAGE):latest\n"

## sql-db-build-fresh: Build arc-sql-db with --no-cache (clean rebuild)
sql-db-build-fresh: BUILD_FLAGS = --no-cache
sql-db-build-fresh: sql-db-build

## sql-db-up: Start arc-sql-db (PostgreSQL 17) in Docker
sql-db-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-sql-db...\n"
	$(COMPOSE_SQL_DB) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sql-db started — PostgreSQL on :5432\n"

## sql-db-down: Stop arc-sql-db container; data volume preserved
sql-db-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-sql-db...\n"
	$(COMPOSE_SQL_DB) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use sql-db-clean to remove data)\n"

## sql-db-health: Probe arc-sql-db health (pg_isready :5432)
sql-db-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Oracle health (:5432)... " && \
	  if docker exec arc-sql-db pg_isready -U arc > /dev/null 2>&1; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## sql-db-logs: Stream arc-sql-db container logs
sql-db-logs:
	$(COMPOSE_SQL_DB) logs -f

## sql-db-clean: [DESTRUCTIVE] Remove arc-sql-db container and data volume
sql-db-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-sql-db container + arc-sql-db-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SQL_DB) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sql-db environment cleaned\n"

## sql-db-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
sql-db-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL sql-db state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_SQL_DB) down --volumes --remove-orphans
	@docker rmi $(SQL_DB_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sql-db reset complete — rebuild: make sql-db-build && make sql-db-up\n"

## sql-db-push: Push arc-sql-db:latest to ghcr.io (requires: docker login ghcr.io)
sql-db-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(SQL_DB_IMAGE):latest...\n"
	@docker push $(SQL_DB_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(SQL_DB_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## sql-db-publish: Push arc-sql-db:latest to ghcr.io (visibility must be set via GitHub UI)
sql-db-publish: sql-db-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sql-db pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-sql-db/settings\n"

## sql-db-tag: Tag arc-sql-db:latest with a version (usage: make sql-db-tag SQL_DB_VERSION=data-v0.1.0)
sql-db-tag:
	@[ -n "$(SQL_DB_VERSION)" ] && [ "$(SQL_DB_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set SQL_DB_VERSION, e.g. make sql-db-tag SQL_DB_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(SQL_DB_IMAGE):latest $(SQL_DB_IMAGE):$(SQL_DB_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(SQL_DB_IMAGE):latest → $(SQL_DB_IMAGE):$(SQL_DB_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
