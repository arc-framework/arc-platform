# ─── Sherlock Reasoning Service (arc-sherlock) ────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

# REGISTRY, ORG, BUILD_FLAGS, COLOR_* macros inherited from root Makefile
COMPOSE_REASONER  := docker compose -f services/reasoner/docker-compose.yml
REASONER_IMAGE    := $(REGISTRY)/$(ORG)/arc-sherlock
REASONER_VERSION ?= latest
REASONER_DIR      := services/reasoner

.PHONY: reasoner-help reasoner-build reasoner-build-fresh reasoner-push reasoner-publish \
        reasoner-tag reasoner-up reasoner-down reasoner-health reasoner-logs \
        reasoner-test reasoner-test-cover reasoner-lint reasoner-check \
        reasoner-clean reasoner-nuke

## reasoner-help: Sherlock reasoning engine (arc-sherlock — LangGraph + Qdrant + NATS)
reasoner-help:
	@printf "\033[1mReasoner (Sherlock) targets\033[0m\n\n"
	@grep -h "^## reasoner-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

# ─── Build ────────────────────────────────────────────────────────────────────

## reasoner-build: Build arc-sherlock image locally using cache (fast)
reasoner-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-sherlock...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REASONER_IMAGE):latest \
	  -f services/reasoner/Dockerfile \
	  services/reasoner/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(REASONER_IMAGE):latest\n"

## reasoner-build-fresh: Build arc-sherlock with --no-cache (clean rebuild)
reasoner-build-fresh: BUILD_FLAGS = --no-cache
reasoner-build-fresh: reasoner-build

## reasoner-push: Push arc-sherlock:latest to ghcr.io (requires: docker login ghcr.io)
reasoner-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(REASONER_IMAGE):latest...\n"
	@docker push $(REASONER_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(REASONER_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## reasoner-publish: Push arc-sherlock:latest to ghcr.io
reasoner-publish: reasoner-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sherlock pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-sherlock/settings\n"

## reasoner-tag: Tag arc-sherlock:latest with a version (usage: make reasoner-tag REASONER_VERSION=v0.1.0)
reasoner-tag:
	@[ -n "$(REASONER_VERSION)" ] && [ "$(REASONER_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set REASONER_VERSION, e.g. make reasoner-tag REASONER_VERSION=v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(REASONER_IMAGE):latest $(REASONER_IMAGE):$(REASONER_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(REASONER_IMAGE):latest → $(REASONER_IMAGE):$(REASONER_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }

# ─── Docker Compose ───────────────────────────────────────────────────────────

## reasoner-up: Start arc-sherlock in Docker (requires arc_platform_net + arc_otel_net)
reasoner-up: reasoner-build
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-sherlock...\n"
	$(COMPOSE_REASONER) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-sherlock started — API on http://localhost:8083\n"

## reasoner-down: Stop arc-sherlock container
reasoner-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-sherlock...\n"
	$(COMPOSE_REASONER) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped\n"

## reasoner-health: Check arc-sherlock liveness endpoint
reasoner-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking arc-sherlock health...\n"
	@curl -sf http://localhost:8083/health \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Healthy\n" \
	  || { printf "$(COLOR_ERR)✗ Health check failed$(COLOR_OFF)\n"; exit 1; }

## reasoner-logs: Stream arc-sherlock container logs
reasoner-logs:
	$(COMPOSE_REASONER) logs -f

# ─── Development ──────────────────────────────────────────────────────────────

## reasoner-test: Run pytest test suite (no live services required)
reasoner-test:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running sherlock tests...\n"
	@cd $(REASONER_DIR) && python -m pytest tests/ -v \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) All sherlock tests passed\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## reasoner-test-cover: Run tests with coverage report
reasoner-test-cover:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running sherlock tests with coverage...\n"
	@cd $(REASONER_DIR) && python -m pytest tests/ --cov=sherlock --cov-report=term-missing \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Coverage report generated\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## reasoner-lint: Run ruff + mypy on src/
reasoner-lint:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Linting sherlock...\n"
	@cd $(REASONER_DIR) && ruff check src/ \
	  && mypy src/ \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Lint passed\n" \
	  || { printf "$(COLOR_ERR)✗ Lint failed$(COLOR_OFF)\n"; exit 1; }

## reasoner-check: Run tests + lint (mirrors CI quality gate)
reasoner-check: reasoner-test reasoner-lint

# ─── Cleanup ──────────────────────────────────────────────────────────────────

## reasoner-clean: Remove compiled Python artifacts and coverage reports
reasoner-clean:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Cleaning sherlock artifacts...\n"
	@find $(REASONER_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find $(REASONER_DIR) -name "*.pyc" -delete 2>/dev/null; true
	@rm -f $(REASONER_DIR)/.coverage $(REASONER_DIR)/coverage.xml
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Cleaned\n"

## reasoner-nuke: Stop container + remove image + clean artifacts
reasoner-nuke: reasoner-down reasoner-clean
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Removing arc-sherlock image...\n"
	@docker rmi $(REASONER_IMAGE):latest 2>/dev/null \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Image removed\n" \
	  || printf "$(COLOR_INFO)→$(COLOR_OFF) Image not found (already removed)\n"
