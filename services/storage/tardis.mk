# ─── Tardis: MinIO Object Storage (arc-storage) ────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_TARDIS := docker compose -f services/storage/docker-compose.yml
TARDIS_IMAGE   := $(REGISTRY)/$(ORG)/arc-storage

.PHONY: tardis-help tardis-build tardis-build-fresh tardis-push tardis-publish tardis-tag \
        tardis-up tardis-down tardis-health tardis-logs tardis-clean tardis-nuke

## tardis-help: MinIO S3-compatible object storage (arc-storage)
tardis-help:
	@printf "\033[1mTardis targets\033[0m\n\n"
	@grep -h "^## tardis-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## tardis-build: Build arc-storage image locally using cache (fast)
tardis-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-storage...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(TARDIS_IMAGE):latest \
	  -f services/storage/Dockerfile \
	  services/storage/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(TARDIS_IMAGE):latest\n"

## tardis-build-fresh: Build arc-storage with --no-cache (clean rebuild)
tardis-build-fresh: BUILD_FLAGS = --no-cache
tardis-build-fresh: tardis-build

## tardis-up: Start arc-storage (MinIO) in Docker
tardis-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-storage...\n"
	$(COMPOSE_TARDIS) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage started — S3 API on :9000, Console on :9001\n"

## tardis-down: Stop arc-storage container; data volume preserved
tardis-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-storage...\n"
	$(COMPOSE_TARDIS) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use tardis-clean to remove data)\n"

## tardis-health: Probe arc-storage health (/minio/health/live :9000)
tardis-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tardis health (:9000)... " && \
	  if curl -sf http://localhost:9000/minio/health/live > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## tardis-logs: Stream arc-storage container logs
tardis-logs:
	$(COMPOSE_TARDIS) logs -f

## tardis-clean: [DESTRUCTIVE] Remove arc-storage container and data volume
tardis-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-storage container + arc-storage-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_TARDIS) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage environment cleaned\n"

## tardis-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
tardis-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL tardis state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_TARDIS) down --volumes --remove-orphans
	@docker rmi $(TARDIS_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage reset complete — rebuild: make tardis-build && make tardis-up\n"

## tardis-push: Push arc-storage:latest to ghcr.io (requires: docker login ghcr.io)
tardis-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(TARDIS_IMAGE):latest...\n"
	@docker push $(TARDIS_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(TARDIS_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## tardis-publish: Push arc-storage:latest to ghcr.io (visibility must be set via GitHub UI)
tardis-publish: tardis-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-storage/settings\n"

## tardis-tag: Tag arc-storage:latest with a version (usage: make tardis-tag TARDIS_VERSION=data-v0.1.0)
tardis-tag:
	@[ -n "$(TARDIS_VERSION)" ] && [ "$(TARDIS_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set TARDIS_VERSION, e.g. make tardis-tag TARDIS_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(TARDIS_IMAGE):latest $(TARDIS_IMAGE):$(TARDIS_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(TARDIS_IMAGE):latest → $(TARDIS_IMAGE):$(TARDIS_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
