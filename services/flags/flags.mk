# ─── Mystique: Unleash Feature Flags (arc-flags) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_FLAGS := docker compose -f services/flags/docker-compose.yml
FLAGS_IMAGE   := $(REGISTRY)/$(ORG)/arc-flags

.PHONY: flags-help flags-build flags-build-fresh flags-push flags-publish flags-tag \
        flags-up flags-down flags-health flags-logs flags-clean flags-nuke

## flags-help: Unleash feature flags (arc-flags)
flags-help:
	@printf "\033[1mMystique targets\033[0m\n\n"
	@grep -h "^## flags-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Requires arc-sql-db and arc-cache to be running\n"
	@printf "  State is stored in Oracle (Postgres) — no local volume.\n\n"

## flags-build: Build arc-flags image locally using cache (fast)
flags-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-flags...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(FLAGS_IMAGE):latest \
	  -f services/flags/Dockerfile \
	  services/flags/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(FLAGS_IMAGE):latest\n"

## flags-build-fresh: Build arc-flags with --no-cache (clean rebuild)
flags-build-fresh: BUILD_FLAGS = --no-cache
flags-build-fresh: flags-build

## flags-up: Start arc-flags (Unleash) in Docker
flags-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-flags...\n"
	$(COMPOSE_FLAGS) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags started — Unleash UI on :4242 (requires arc-sql-db + arc-cache)\n"

## flags-down: Stop arc-flags container; no volume to preserve (stateless)
flags-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-flags...\n"
	$(COMPOSE_FLAGS) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (state lives in Oracle — no local volume)\n"

## flags-health: Probe arc-flags health endpoint (:4242/health)
flags-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Mystique health (:4242)... " && \
	  if curl -sf http://localhost:4242/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## flags-logs: Stream arc-flags container logs
flags-logs:
	$(COMPOSE_FLAGS) logs -f

## flags-clean: [DESTRUCTIVE] Remove arc-flags container (stateless — no volume)
flags-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-flags container (state is in Oracle, not a local volume).\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLAGS) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags container removed\n"

## flags-nuke: [DESTRUCTIVE] Full reset — container and local image
flags-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys arc-flags container and local image (Oracle data unaffected).\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_FLAGS) down --remove-orphans
	@docker rmi $(FLAGS_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags reset complete — rebuild: make flags-build && make flags-up\n"

## flags-push: Push arc-flags:latest to ghcr.io (requires: docker login ghcr.io)
flags-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(FLAGS_IMAGE):latest...\n"
	@docker push $(FLAGS_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(FLAGS_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## flags-publish: Push arc-flags:latest to ghcr.io (visibility must be set via GitHub UI)
flags-publish: flags-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-flags/settings\n"

## flags-tag: Tag arc-flags:latest with a version (usage: make flags-tag FLAGS_VERSION=flags-v0.1.0)
flags-tag:
	@[ -n "$(FLAGS_VERSION)" ] && [ "$(FLAGS_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set FLAGS_VERSION, e.g. make flags-tag FLAGS_VERSION=flags-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(FLAGS_IMAGE):latest $(FLAGS_IMAGE):$(FLAGS_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(FLAGS_IMAGE):latest → $(FLAGS_IMAGE):$(FLAGS_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
