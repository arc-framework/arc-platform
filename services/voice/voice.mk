# ─── Voice Service (arc-voice-agent / Scarlett) ───────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

# REGISTRY, ORG, BUILD_FLAGS, COLOR_* macros inherited from root Makefile
# docker-compose.yml is created in TASK-070; voice-up/down/logs targets require it.
COMPOSE_VOICE  := docker compose -f services/voice/docker-compose.yml
VOICE_IMAGE    := $(REGISTRY)/$(ORG)/arc-voice-agent
VOICE_VERSION ?= latest
VOICE_DIR      := services/voice

.PHONY: voice-help voice-build voice-build-fresh voice-push voice-publish \
        voice-tag voice-up voice-down voice-health voice-logs \
        voice-test voice-test-cover voice-lint voice-check \
        voice-clean voice-nuke

## voice-help: Voice agent (arc-voice-agent — Scarlett, LiveKit + Whisper + Piper)
voice-help:
	@printf "\033[1mVoice targets\033[0m\n\n"
	@grep -h "^## voice-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

# ─── Build ────────────────────────────────────────────────────────────────────

## voice-build: Build arc-voice-agent image locally using cache (fast)
voice-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-voice-agent...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(VOICE_IMAGE):latest \
	  -f services/voice/Dockerfile \
	  services/voice/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(VOICE_IMAGE):latest\n"

## voice-build-fresh: Build arc-voice-agent with --no-cache (clean rebuild)
voice-build-fresh: BUILD_FLAGS = --no-cache
voice-build-fresh: voice-build

## voice-push: Push arc-voice-agent:latest to ghcr.io (requires: docker login ghcr.io)
voice-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(VOICE_IMAGE):latest...\n"
	@docker push $(VOICE_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(VOICE_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## voice-publish: Push arc-voice-agent:latest to ghcr.io
voice-publish: voice-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-voice-agent pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-voice-agent/settings\n"

## voice-tag: Tag arc-voice-agent:latest with a version (usage: make voice-tag VOICE_VERSION=v0.1.0)
voice-tag:
	@[ -n "$(VOICE_VERSION)" ] && [ "$(VOICE_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set VOICE_VERSION, e.g. make voice-tag VOICE_VERSION=v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(VOICE_IMAGE):latest $(VOICE_IMAGE):$(VOICE_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(VOICE_IMAGE):latest → $(VOICE_IMAGE):$(VOICE_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }

# ─── Docker Compose ───────────────────────────────────────────────────────────

## voice-up: Start arc-voice-agent in Docker (requires arc_platform_net + arc_otel_net)
voice-up: voice-build
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-voice-agent...\n"
	$(COMPOSE_VOICE) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-voice-agent started — API on http://localhost:8803\n"

## voice-down: Stop arc-voice-agent container
voice-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-voice-agent...\n"
	$(COMPOSE_VOICE) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped\n"

## voice-health: Check arc-voice-agent liveness endpoint
voice-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Checking arc-voice-agent health...\n"
	@curl -sf http://localhost:8803/health \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Healthy\n" \
	  || { printf "$(COLOR_ERR)✗ Health check failed$(COLOR_OFF)\n"; exit 1; }

## voice-logs: Stream arc-voice-agent container logs
voice-logs:
	$(COMPOSE_VOICE) logs -f

# ─── Development ──────────────────────────────────────────────────────────────

## voice-test: Run pytest test suite (no live services required)
voice-test:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running voice tests...\n"
	@cd $(VOICE_DIR) && uv run python -m pytest tests/ -v \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) All voice tests passed\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## voice-test-cover: Run tests with coverage report
voice-test-cover:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running voice tests with coverage...\n"
	@cd $(VOICE_DIR) && uv run python -m pytest tests/ --cov=voice --cov-report=term-missing \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Coverage report generated\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## voice-lint: Run ruff + mypy on src/
voice-lint:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Linting voice service...\n"
	@cd $(VOICE_DIR) && uv run ruff check src/ \
	  && uv run mypy src/ \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Lint passed\n" \
	  || { printf "$(COLOR_ERR)✗ Lint failed$(COLOR_OFF)\n"; exit 1; }

## voice-check: Run tests + lint (mirrors CI quality gate)
voice-check: voice-test voice-lint

# ─── Cleanup ──────────────────────────────────────────────────────────────────

## voice-clean: Remove compiled Python artifacts and coverage reports
voice-clean:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Cleaning voice artifacts...\n"
	@find $(VOICE_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find $(VOICE_DIR) -name "*.pyc" -delete 2>/dev/null; true
	@rm -f $(VOICE_DIR)/.coverage $(VOICE_DIR)/coverage.xml
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Cleaned\n"

## voice-nuke: Stop container + remove image + clean artifacts
voice-nuke: voice-down voice-clean
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Removing arc-voice-agent image...\n"
	@docker rmi $(VOICE_IMAGE):latest 2>/dev/null \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Image removed\n" \
	  || printf "$(COLOR_INFO)→$(COLOR_OFF) Image not found (already removed)\n"
