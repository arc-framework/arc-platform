# ─── A.R.C. Platform — Root Makefile ─────────────────────────────────────────
# Single entrypoint for all service orchestration.
# All paths are relative to the repo root — no cd commands used.
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE      := docker compose
# Combined file: all otel services in one compose, paths relative to services/otel/
COMPOSE_OTEL := $(COMPOSE) -f services/otel/docker-compose.yml

# Default SigNoz local-dev credentials (override via env if needed)
SIGNOZ_NAME     ?= Admin
SIGNOZ_ORG      ?= ARC
SIGNOZ_EMAIL    ?= admin@arc.local
SIGNOZ_PASSWORD ?= Admin@Arc123!

# ─── OTEL Stack ───────────────────────────────────────────────────────────────

.PHONY: otel-up otel-down otel-health otel-logs otel-ps otel-user

## otel-up: Start the full OTEL stack and seed the default admin user
otel-up:
	$(COMPOSE_OTEL) up -d
	@echo "Waiting for SigNoz to become ready (this takes ~3-5 min on first run)..."
	@until curl -sf http://localhost:3301/api/v1/health > /dev/null 2>&1; do \
	  printf "."; sleep 5; \
	done
	@echo " ready"
	@$(MAKE) otel-user --no-print-directory

## otel-down: Stop and remove all OTEL stack containers
otel-down:
	$(COMPOSE_OTEL) down

## otel-health: Probe both health endpoints; exits non-zero if either fails
otel-health:
	@echo "Checking OTEL collector health (:13133)..." && \
	if curl -sf http://localhost:13133/ > /dev/null; then \
		echo "✓ Collector health (:13133) OK"; \
	else \
		echo "✗ Collector health (:13133) FAILED"; exit 1; \
	fi
	@echo "Checking SigNoz health (:3301)..." && \
	if curl -sf http://localhost:3301/api/v1/health > /dev/null; then \
		echo "✓ SigNoz health (:3301) OK"; \
	else \
		echo "✗ SigNoz health (:3301) FAILED"; exit 1; \
	fi

## otel-logs: Stream logs from all OTEL containers
otel-logs:
	$(COMPOSE_OTEL) logs -f

## otel-ps: Show OTEL container status
otel-ps:
	$(COMPOSE_OTEL) ps

## otel-build: Build all ARC otel images locally (required before first otel-up)
## Uses the host architecture automatically (amd64 or arm64)
otel-build:
	docker build \
	  -t ghcr.io/arc-framework/arc-zookeeper:latest \
	  -f services/otel/observability/zookeeper.Dockerfile \
	  services/otel/observability/
	docker build \
	  --build-arg TARGETARCH=$(shell uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') \
	  -t ghcr.io/arc-framework/arc-clickhouse:latest \
	  -f services/otel/observability/clickhouse.Dockerfile \
	  services/otel/observability/
	docker build \
	  -t ghcr.io/arc-framework/friday:latest \
	  -f services/otel/observability/Dockerfile \
	  services/otel/observability/
	docker build \
	  -t ghcr.io/arc-framework/widow:latest \
	  -f services/otel/telemetry/Dockerfile \
	  services/otel/telemetry/

## otel-user: Create the default SigNoz admin user (idempotent — skips if already exists)
## Override: make otel-user SIGNOZ_EMAIL=you@example.com SIGNOZ_PASSWORD=secret
otel-user:
	@echo "Creating SigNoz admin user ($(SIGNOZ_EMAIL))..."
	@curl -sf http://localhost:3301/api/v1/register \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(SIGNOZ_NAME)\",\"orgName\":\"$(SIGNOZ_ORG)\",\"email\":\"$(SIGNOZ_EMAIL)\",\"password\":\"$(SIGNOZ_PASSWORD)\"}" \
	  | grep -q '"accessJwt"' \
	  && echo "✓ User created — login at http://localhost:3301" \
	  || echo "✗ User already exists or SigNoz not ready yet (run: make otel-health)"
