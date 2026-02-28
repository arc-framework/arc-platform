# ─── Nick Fury: OpenBao Secrets Management (arc-vault) ───────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# Dev mode only — all secrets lost on restart (stateless, in-memory OpenBao).
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_NICK_FURY := docker compose -f services/secrets/docker-compose.yml
NICK_FURY_IMAGE   := $(REGISTRY)/$(ORG)/arc-vault

.PHONY: nick-fury-help nick-fury-build nick-fury-build-fresh nick-fury-push nick-fury-publish nick-fury-tag \
        nick-fury-up nick-fury-down nick-fury-health nick-fury-logs nick-fury-clean nick-fury-nuke

## nick-fury-help: OpenBao secrets management — Dev mode only — all secrets lost on restart
nick-fury-help:
	@printf "\033[1mNick Fury targets\033[0m\n\n"
	@grep -h "^## nick-fury-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Dev mode only — all secrets lost on restart.\n"
	@printf "  Default root token: arc-dev-token  |  API: http://localhost:8200\n\n"

## nick-fury-build: Build arc-vault image locally using cache (fast)
nick-fury-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-vault...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(NICK_FURY_IMAGE):latest \
	  -f services/secrets/Dockerfile \
	  services/secrets/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(NICK_FURY_IMAGE):latest\n"

## nick-fury-build-fresh: Build arc-vault with --no-cache (clean rebuild)
nick-fury-build-fresh: BUILD_FLAGS = --no-cache
nick-fury-build-fresh: nick-fury-build

## nick-fury-up: Start arc-vault (OpenBao) in Docker — dev mode, token: arc-dev-token
nick-fury-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-vault...\n"
	$(COMPOSE_NICK_FURY) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault started — OpenBao dev mode on :8200 (token: arc-dev-token)\n"

## nick-fury-down: Stop arc-vault container (stateless — no volume to preserve)
nick-fury-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-vault...\n"
	$(COMPOSE_NICK_FURY) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (stateless service — all secrets already lost)\n"

## nick-fury-health: Probe arc-vault health endpoint (:8200/v1/sys/health)
nick-fury-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Nick Fury health (:8200)... " && \
	  if curl -sf http://localhost:8200/v1/sys/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## nick-fury-logs: Stream arc-vault container logs
nick-fury-logs:
	$(COMPOSE_NICK_FURY) logs -f

## nick-fury-clean: [DESTRUCTIVE] Remove arc-vault container (no volume — stateless)
nick-fury-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-vault container (stateless — no volume).\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_NICK_FURY) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault environment cleaned\n"

## nick-fury-nuke: [DESTRUCTIVE] Full reset — container and local image (all secrets will be lost)
nick-fury-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) All secrets will be lost (stateless dev service).\n"
	@printf "  Destroys: arc-vault container + local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_NICK_FURY) down --remove-orphans
	@docker rmi $(NICK_FURY_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault reset complete — rebuild: make nick-fury-build && make nick-fury-up\n"

## nick-fury-push: Push arc-vault:latest to ghcr.io (requires: docker login ghcr.io)
nick-fury-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(NICK_FURY_IMAGE):latest...\n"
	@docker push $(NICK_FURY_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(NICK_FURY_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## nick-fury-publish: Push arc-vault:latest to ghcr.io (visibility must be set via GitHub UI)
nick-fury-publish: nick-fury-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-vault/settings\n"

## nick-fury-tag: Tag arc-vault:latest with a version (usage: make nick-fury-tag NICK_FURY_VERSION=secrets-v0.1.0)
nick-fury-tag:
	@[ -n "$(NICK_FURY_VERSION)" ] && [ "$(NICK_FURY_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set NICK_FURY_VERSION, e.g. make nick-fury-tag NICK_FURY_VERSION=secrets-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(NICK_FURY_IMAGE):latest $(NICK_FURY_IMAGE):$(NICK_FURY_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(NICK_FURY_IMAGE):latest → $(NICK_FURY_IMAGE):$(NICK_FURY_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
