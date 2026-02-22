# ─── Cortex Bootstrap Service (arc-cortex) ───────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

# REGISTRY, ORG, BUILD_FLAGS inherited from root Makefile / otel.mk
COMPOSE_CORTEX := docker compose -f services/cortex/docker-compose.yml
CORTEX_IMAGE   := $(REGISTRY)/$(ORG)/arc-cortex
CORTEX_VERSION ?= latest
CORTEX_DIR     := services/cortex
CORTEX_BIN     := bin/cortex

# Local infra endpoints — override via env vars (CORTEX_*) or a config file.
# These defaults point to localhost equivalents of the Docker service hostnames.
CORTEX_LOCAL_ENV := \
  CORTEX_BOOTSTRAP_POSTGRES_HOST=localhost \
  CORTEX_BOOTSTRAP_NATS_URL=nats://localhost:4222 \
  CORTEX_BOOTSTRAP_PULSAR_ADMIN_URL=http://localhost:8080 \
  CORTEX_BOOTSTRAP_REDIS_HOST=localhost \
  CORTEX_TELEMETRY_OTLP_ENDPOINT=
# ^ empty endpoint disables OTEL — avoids 10s periodic-reader noise when no collector is running.
# To enable with arc-friday-collector: make cortex-run CORTEX_TELEMETRY_OTLP_ENDPOINT=127.0.0.1:4317

.PHONY: cortex-help cortex-build cortex-build-fresh cortex-push cortex-publish cortex-tag \
        cortex-bin cortex-run cortex-run-dev cortex-bootstrap-local cortex-test cortex-lint cortex-check \
        cortex-docker-up cortex-docker-down cortex-docker-logs cortex-docker-ps cortex-docker-bootstrap

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

# ─── Local Development ────────────────────────────────────────────────────────

## cortex-test: Run all Cortex tests with the race detector
cortex-test:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running cortex tests...\n"
	@cd $(CORTEX_DIR) && go test ./... -count=1 -race \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) All cortex tests passed\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## cortex-test-cover: Run tests with a per-package coverage summary
cortex-test-cover:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running cortex tests with coverage...\n"
	@cd $(CORTEX_DIR) && go test ./... -count=1 -coverprofile=coverage.out \
	  && go tool cover -func=coverage.out | tail -1 \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Coverage report: $(CORTEX_DIR)/coverage.out\n" \
	  || { printf "$(COLOR_ERR)✗ Tests failed$(COLOR_OFF)\n"; exit 1; }

## cortex-lint: Run golangci-lint on the Cortex module
cortex-lint:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Linting cortex...\n"
	@cd $(CORTEX_DIR) && golangci-lint run ./... \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Lint passed\n" \
	  || { printf "$(COLOR_ERR)✗ Lint failed$(COLOR_OFF)\n"; exit 1; }

## cortex-check: Run tests + lint (mirrors CI quality gate)
cortex-check: cortex-test cortex-lint

## cortex-bin: Compile a local cortex binary to bin/cortex (for ad-hoc local runs)
cortex-bin:
	@mkdir -p bin
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building cortex binary → $(CORTEX_BIN)\n"
	@cd $(CORTEX_DIR) && go build -o ../../$(CORTEX_BIN) ./cmd/cortex \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Binary ready: $(CORTEX_BIN)\n" \
	  || { printf "$(COLOR_ERR)✗ Build failed$(COLOR_OFF)\n"; exit 1; }

## cortex-run: Start the cortex server locally against localhost infra (Ctrl-C to stop)
## Override any endpoint: CORTEX_BOOTSTRAP_POSTGRES_HOST=myhost make cortex-run
cortex-run: cortex-bin
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting cortex server on :8081 (localhost infra)...\n"
	@printf "  Override endpoints via CORTEX_* env vars — see cortex-help for defaults.\n"
	@$(CORTEX_LOCAL_ENV) $(CORTEX_BIN) server

## cortex-run-dev: Start cortex locally with all dev services (localhost infra + OTEL). Requires: make otel-up
cortex-run-dev: cortex-bin
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting cortex server on :8081 (localhost infra + OTEL)...\n"
	@printf "  Traces/metrics → arc-friday-collector at 127.0.0.1:4317\n"
	@printf "  API docs       → http://localhost:8081/api-docs\n"
	@$(CORTEX_LOCAL_ENV) CORTEX_TELEMETRY_OTLP_ENDPOINT=127.0.0.1:4317 $(CORTEX_BIN) server

## cortex-bootstrap-local: Run one-shot bootstrap against localhost infra and print JSON result
## Override any endpoint: CORTEX_BOOTSTRAP_POSTGRES_HOST=myhost make cortex-bootstrap-local
cortex-bootstrap-local: cortex-bin
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running cortex bootstrap against localhost infra...\n"
	@$(CORTEX_LOCAL_ENV) $(CORTEX_BIN) bootstrap

# ─── Docker Compose ───────────────────────────────────────────────────────────
# Requires: make otel-up (creates arc_otel_net) and the platform infra stack
# (creates arc_net with arc-oracle, arc-flash, arc-sonic, arc-strange).
# Service names resolve automatically inside Docker — no env var overrides needed.

## cortex-docker-up: Start arc-cortex in Docker (requires arc_otel_net + arc_net)
cortex-docker-up: cortex-build
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-cortex in Docker...\n"
	$(COMPOSE_CORTEX) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-cortex started — API on http://localhost:8081\n"

## cortex-docker-down: Stop arc-cortex container
cortex-docker-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-cortex...\n"
	$(COMPOSE_CORTEX) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped\n"

## cortex-docker-logs: Stream arc-cortex logs
cortex-docker-logs:
	$(COMPOSE_CORTEX) logs -f

## cortex-docker-ps: Show arc-cortex container status
cortex-docker-ps:
	$(COMPOSE_CORTEX) ps

## cortex-docker-bootstrap: Run one-shot bootstrap inside the running Docker container
cortex-docker-bootstrap:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running bootstrap inside arc-cortex container...\n"
	@docker exec arc-cortex /usr/local/bin/cortex bootstrap
