# ─── Mystique: Unleash Feature Flags (arc-flags) ──────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_MYSTIQUE := docker compose -f services/flags/docker-compose.yml
MYSTIQUE_IMAGE   := $(REGISTRY)/$(ORG)/arc-flags

.PHONY: mystique-help mystique-build mystique-build-fresh mystique-push mystique-publish mystique-tag \
        mystique-up mystique-down mystique-health mystique-logs mystique-clean mystique-nuke

## mystique-help: Unleash feature flags (arc-flags)
mystique-help:
	@printf "\033[1mMystique targets\033[0m\n\n"
	@grep -h "^## mystique-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Requires arc-sql-db and arc-cache to be running\n"
	@printf "  State is stored in Oracle (Postgres) — no local volume.\n\n"

## mystique-build: Build arc-flags image locally using cache (fast)
mystique-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-flags...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(MYSTIQUE_IMAGE):latest \
	  -f services/flags/Dockerfile \
	  services/flags/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(MYSTIQUE_IMAGE):latest\n"

## mystique-build-fresh: Build arc-flags with --no-cache (clean rebuild)
mystique-build-fresh: BUILD_FLAGS = --no-cache
mystique-build-fresh: mystique-build

## mystique-up: Start arc-flags (Unleash) in Docker
mystique-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-flags...\n"
	$(COMPOSE_MYSTIQUE) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags started — Unleash UI on :4242 (requires arc-sql-db + arc-cache)\n"

## mystique-down: Stop arc-flags container; no volume to preserve (stateless)
mystique-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-flags...\n"
	$(COMPOSE_MYSTIQUE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (state lives in Oracle — no local volume)\n"

## mystique-health: Probe arc-flags health endpoint (:4242/health)
mystique-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Mystique health (:4242)... " && \
	  if curl -sf http://localhost:4242/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## mystique-logs: Stream arc-flags container logs
mystique-logs:
	$(COMPOSE_MYSTIQUE) logs -f

## mystique-clean: [DESTRUCTIVE] Remove arc-flags container (stateless — no volume)
mystique-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-flags container (state is in Oracle, not a local volume).\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_MYSTIQUE) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags container removed\n"

## mystique-nuke: [DESTRUCTIVE] Full reset — container and local image
mystique-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys arc-flags container and local image (Oracle data unaffected).\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_MYSTIQUE) down --remove-orphans
	@docker rmi $(MYSTIQUE_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags reset complete — rebuild: make mystique-build && make mystique-up\n"

## mystique-push: Push arc-flags:latest to ghcr.io (requires: docker login ghcr.io)
mystique-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(MYSTIQUE_IMAGE):latest...\n"
	@docker push $(MYSTIQUE_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(MYSTIQUE_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## mystique-publish: Push arc-flags:latest to ghcr.io (visibility must be set via GitHub UI)
mystique-publish: mystique-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-flags pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-flags/settings\n"

## mystique-tag: Tag arc-flags:latest with a version (usage: make mystique-tag MYSTIQUE_VERSION=flags-v0.1.0)
mystique-tag:
	@[ -n "$(MYSTIQUE_VERSION)" ] && [ "$(MYSTIQUE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set MYSTIQUE_VERSION, e.g. make mystique-tag MYSTIQUE_VERSION=flags-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(MYSTIQUE_IMAGE):latest $(MYSTIQUE_IMAGE):$(MYSTIQUE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(MYSTIQUE_IMAGE):latest → $(MYSTIQUE_IMAGE):$(MYSTIQUE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
