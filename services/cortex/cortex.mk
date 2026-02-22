# ─── Cortex Bootstrap Service (arc-cortex) ───────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

# REGISTRY, ORG, BUILD_FLAGS inherited from root Makefile / otel.mk
CORTEX_IMAGE   := $(REGISTRY)/$(ORG)/arc-cortex
CORTEX_VERSION ?= latest

.PHONY: cortex-help cortex-build cortex-build-fresh cortex-push cortex-publish cortex-tag

## cortex-help: Cortex bootstrap service (arc-cortex — provisions Postgres, NATS, Pulsar, Redis)
cortex-help:
	@printf "\033[1mCortex targets\033[0m\n\n"
	@grep -h "^## cortex-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## cortex-build: Build arc-cortex image locally using cache (fast)
cortex-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-cortex...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(CORTEX_IMAGE):latest \
	  -f services/cortex/Dockerfile \
	  services/cortex/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(CORTEX_IMAGE):latest\n"

## cortex-build-fresh: Build arc-cortex with --no-cache (clean rebuild)
cortex-build-fresh: BUILD_FLAGS = --no-cache
cortex-build-fresh: cortex-build

## cortex-push: Push arc-cortex:latest to ghcr.io (requires: docker login ghcr.io)
cortex-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(CORTEX_IMAGE):latest...\n"
	@docker push $(CORTEX_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(CORTEX_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## cortex-publish: Push image and set GHCR package to public (requires: gh auth with write:packages)
cortex-publish: cortex-push
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Setting arc-cortex package to public...\n"
	@gh api \
	  --method PATCH \
	  -H "Accept: application/vnd.github+json" \
	  "/orgs/$(ORG)/packages/container/arc-cortex" \
	  -f visibility=public \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cortex → public at ghcr.io/$(ORG)/arc-cortex\n" \
	  || printf "$(COLOR_ERR)✗$(COLOR_OFF) Failed — run: gh auth status\n"

## cortex-tag: Tag arc-cortex:latest with a version (usage: make cortex-tag CORTEX_VERSION=cortex-v0.1.0)
cortex-tag:
	@[ -n "$(CORTEX_VERSION)" ] && [ "$(CORTEX_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set CORTEX_VERSION, e.g. make cortex-tag CORTEX_VERSION=cortex-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(CORTEX_IMAGE):latest $(CORTEX_IMAGE):$(CORTEX_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(CORTEX_IMAGE):latest → $(CORTEX_IMAGE):$(CORTEX_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }
