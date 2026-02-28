# ─── Tardis: MinIO Object Storage (arc-storage) ────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_STORAGE := docker compose -f services/storage/docker-compose.yml
STORAGE_IMAGE   := $(REGISTRY)/$(ORG)/arc-storage

.PHONY: storage-help storage-build storage-build-fresh storage-push storage-publish storage-tag \
        storage-up storage-down storage-health storage-logs storage-clean storage-nuke

## storage-help: MinIO S3-compatible object storage (arc-storage)
storage-help:
	@printf "\033[1mTardis targets\033[0m\n\n"
	@grep -h "^## storage-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## storage-build: Build arc-storage image locally using cache (fast)
storage-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-storage...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(STORAGE_IMAGE):latest \
	  -f services/storage/Dockerfile \
	  services/storage/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(STORAGE_IMAGE):latest\n"

## storage-build-fresh: Build arc-storage with --no-cache (clean rebuild)
storage-build-fresh: BUILD_FLAGS = --no-cache
storage-build-fresh: storage-build

## storage-up: Start arc-storage (MinIO) in Docker
storage-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-storage...\n"
	$(COMPOSE_STORAGE) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage started — S3 API on :9000, Console on :9001\n"

## storage-down: Stop arc-storage container; data volume preserved
storage-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-storage...\n"
	$(COMPOSE_STORAGE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volume preserved — use storage-clean to remove data)\n"

## storage-health: Probe arc-storage health (/minio/health/live :9000)
storage-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Tardis health (:9000)... " && \
	  if curl -sf http://localhost:9000/minio/health/live > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## storage-logs: Stream arc-storage container logs
storage-logs:
	$(COMPOSE_STORAGE) logs -f

## storage-clean: [DESTRUCTIVE] Remove arc-storage container and data volume
storage-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-storage container + arc-storage-data volume.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STORAGE) down --volumes --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage environment cleaned\n"

## storage-nuke: [DESTRUCTIVE] Full reset — container, volume, and local image
storage-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL tardis state: container, volume, and local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_STORAGE) down --volumes --remove-orphans
	@docker rmi $(STORAGE_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage reset complete — rebuild: make storage-build && make storage-up\n"

## storage-push: Push arc-storage:latest to ghcr.io (requires: docker login ghcr.io)
storage-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(STORAGE_IMAGE):latest...\n"
	@docker push $(STORAGE_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(STORAGE_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## storage-publish: Push arc-storage:latest to ghcr.io (visibility must be set via GitHub UI)
storage-publish: storage-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-storage pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-storage/settings\n"

## storage-tag: Tag arc-storage:latest with a version (usage: make storage-tag STORAGE_VERSION=data-v0.1.0)
storage-tag:
	@[ -n "$(STORAGE_VERSION)" ] && [ "$(STORAGE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set STORAGE_VERSION, e.g. make storage-tag STORAGE_VERSION=data-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(STORAGE_IMAGE):latest $(STORAGE_IMAGE):$(STORAGE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(STORAGE_IMAGE):latest → $(STORAGE_IMAGE):$(STORAGE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
