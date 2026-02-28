# ─── Oracle: PostgreSQL 17 Persistence (arc-oracle) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_ORACLE := docker compose -f services/persistence/docker-compose.yml
ORACLE_IMAGE   := $(REGISTRY)/$(ORG)/arc-oracle

.PHONY: oracle-help oracle-build oracle-build-fresh oracle-push oracle-publish oracle-tag \
        oracle-up oracle-down oracle-health oracle-logs oracle-clean oracle-nuke

## oracle-help: PostgreSQL 17 persistence (arc-oracle)
oracle-help:
	@printf "\033[1mOracle targets\033[0m\n\n"
	@grep -h "^## oracle-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: POSTGRES_PASSWORD is ignored after data dir is initialized.\n"
	@printf "  To reset credentials: make oracle-nuke && make oracle-up\n\n"

## oracle-build: Build arc-oracle image locally using cache (fast)
oracle-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-oracle...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(ORACLE_IMAGE):latest \
	  -f services/persistence/Dockerfile \
	  services/persistence/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(ORACLE_IMAGE):latest\n"

## oracle-build-fresh: Build arc-oracle with --no-cache (clean rebuild)
oracle-build-fresh: BUILD_FLAGS = --no-cache
oracle-build-fresh: oracle-build

## oracle-up: Start arc-oracle (PostgreSQL 17) in Docker
oracle-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-oracle...\n"
	$(COMPOSE_ORACLE) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-oracle started — PostgreSQL on :5432\n"

## oracle-down: Stop arc-oracle container; data volume preserved
oracle-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-oracle...\n"
	$(COMPOSE_ORACLE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use oracle-clean to remove data)\n"

## oracle-health: Probe arc-oracle health (pg_isready :5432)
oracle-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Oracle health (:5432)... " && \
	  if docker exec arc-oracle pg_isready -U arc > /dev/null 2>&1; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## oracle-logs: Stream arc-oracle container logs
oracle-logs:
	$(COMPOSE_ORACLE) logs -f

## oracle-clean: [DESTRUCTIVE] Remove arc-oracle container and data volume
oracle-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-oracle container + arc-oracle-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_ORACLE) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-oracle environment cleaned\n"

## oracle-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
oracle-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL oracle state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_ORACLE) down --volumes --remove-orphans
	@docker rmi $(ORACLE_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-oracle reset complete — rebuild: make oracle-build && make oracle-up\n"

## oracle-push: Push arc-oracle:latest to ghcr.io (requires: docker login ghcr.io)
oracle-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(ORACLE_IMAGE):latest...\n"
	@docker push $(ORACLE_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(ORACLE_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## oracle-publish: Push arc-oracle:latest to ghcr.io (visibility must be set via GitHub UI)
oracle-publish: oracle-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-oracle pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-oracle/settings\n"

## oracle-tag: Tag arc-oracle:latest with a version (usage: make oracle-tag ORACLE_VERSION=data-v0.1.0)
oracle-tag:
	@[ -n "$(ORACLE_VERSION)" ] && [ "$(ORACLE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set ORACLE_VERSION, e.g. make oracle-tag ORACLE_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(ORACLE_IMAGE):latest $(ORACLE_IMAGE):$(ORACLE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(ORACLE_IMAGE):latest → $(ORACLE_IMAGE):$(ORACLE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
