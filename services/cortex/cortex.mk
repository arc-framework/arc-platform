# ─── Cortex Bootstrap Service (arc-cortex) ───────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

# REGISTRY, ORG, BUILD_FLAGS inherited from root Makefile / otel.mk
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
# To enable: make cortex-run CORTEX_TELEMETRY_OTLP_ENDPOINT=localhost:4317

.PHONY: cortex-help cortex-build cortex-build-fresh cortex-push cortex-publish cortex-tag \
        cortex-bin cortex-run cortex-bootstrap-local cortex-test cortex-lint cortex-check

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

## cortex-bootstrap-local: Run one-shot bootstrap against localhost infra and print JSON result
## Override any endpoint: CORTEX_BOOTSTRAP_POSTGRES_HOST=myhost make cortex-bootstrap-local
cortex-bootstrap-local: cortex-bin
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Running cortex bootstrap against localhost infra...\n"
	@$(CORTEX_LOCAL_ENV) $(CORTEX_BIN) bootstrap
