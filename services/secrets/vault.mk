# ─── Nick Fury: OpenBao Secrets Management (arc-vault) ───────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# Dev mode only — all secrets lost on restart (stateless, in-memory OpenBao).
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_VAULT := docker compose -f services/secrets/docker-compose.yml
VAULT_IMAGE   := $(REGISTRY)/$(ORG)/arc-vault

.PHONY: vault-help vault-build vault-build-fresh vault-push vault-publish vault-tag \
        vault-up vault-down vault-health vault-logs vault-clean vault-nuke

## vault-help: OpenBao secrets management — Dev mode only — all secrets lost on restart
vault-help:
	@printf "\033[1mNick Fury targets\033[0m\n\n"
	@grep -h "^## vault-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n  NOTE: Dev mode only — all secrets lost on restart.\n"
	@printf "  Default root token: arc-dev-token  |  API: http://localhost:8200\n\n"

## vault-build: Build arc-vault image locally using cache (fast)
vault-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-vault...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(VAULT_IMAGE):latest \
	  -f services/secrets/Dockerfile \
	  services/secrets/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(VAULT_IMAGE):latest\n"

## vault-build-fresh: Build arc-vault with --no-cache (clean rebuild)
vault-build-fresh: BUILD_FLAGS = --no-cache
vault-build-fresh: vault-build

## vault-up: Start arc-vault (OpenBao) in Docker — dev mode, token: arc-dev-token
vault-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-vault...\n"
	$(COMPOSE_VAULT) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault started — OpenBao dev mode on :8200 (token: arc-dev-token)\n"

## vault-down: Stop arc-vault container (stateless — no volume to preserve)
vault-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-vault...\n"
	$(COMPOSE_VAULT) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (stateless service — all secrets already lost)\n"

## vault-health: Probe arc-vault health endpoint (:8200/v1/sys/health)
vault-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Nick Fury health (:8200)... " && \
	  if curl -sf http://localhost:8200/v1/sys/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## vault-logs: Stream arc-vault container logs
vault-logs:
	$(COMPOSE_VAULT) logs -f

## vault-clean: [DESTRUCTIVE] Remove arc-vault container (no volume — stateless)
vault-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-vault container (stateless — no volume).\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_VAULT) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault environment cleaned\n"

## vault-nuke: [DESTRUCTIVE] Full reset — container and local image (all secrets will be lost)
vault-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) All secrets will be lost (stateless dev service).\n"
	@printf "  Destroys: arc-vault container + local image.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_VAULT) down --remove-orphans
	@docker rmi $(VAULT_IMAGE):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault reset complete — rebuild: make vault-build && make vault-up\n"

## vault-push: Push arc-vault:latest to ghcr.io (requires: docker login ghcr.io)
vault-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(VAULT_IMAGE):latest...\n"
	@docker push $(VAULT_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(VAULT_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## vault-publish: Push arc-vault:latest to ghcr.io (visibility must be set via GitHub UI)
vault-publish: vault-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-vault pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-vault/settings\n"

## vault-tag: Tag arc-vault:latest with a version (usage: make vault-tag VAULT_VERSION=secrets-v0.1.0)
vault-tag:
	@[ -n "$(VAULT_VERSION)" ] && [ "$(VAULT_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set VAULT_VERSION, e.g. make vault-tag VAULT_VERSION=secrets-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(VAULT_IMAGE):latest $(VAULT_IMAGE):$(VAULT_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(VAULT_IMAGE):latest → $(VAULT_IMAGE):$(VAULT_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
