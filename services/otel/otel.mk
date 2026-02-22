# ─── OTEL Stack (arc-friday-* services) ──────────────────────────────────────
# Included by the root Makefile. All paths are relative to the repo root.
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE_OTEL := docker compose -f services/otel/docker-compose.yml
REGISTRY     := ghcr.io
ORG          := arc-framework

# ARC-managed images — built by otel-build, pushed by otel-push.
# arc-friday-migrator is a controlled re-tag of the upstream schema-migrator.
OTEL_IMAGES := \
  $(REGISTRY)/$(ORG)/arc-friday-zookeeper:latest \
  $(REGISTRY)/$(ORG)/arc-friday-clickhouse:latest \
  $(REGISTRY)/$(ORG)/arc-friday-migrator:latest \
  $(REGISTRY)/$(ORG)/arc-friday:latest \
  $(REGISTRY)/$(ORG)/arc-friday-collector:latest

# Default arc-friday local-dev credentials — override via environment
FRIDAY_NAME     ?= Admin
FRIDAY_ORG      ?= ARC
FRIDAY_EMAIL    ?= admin@arc.local
FRIDAY_PASSWORD ?= Admin@Arc123!

.PHONY: otel-help otel-up otel-up-telemetry otel-up-observability otel-down \
        otel-health otel-logs otel-ps otel-build otel-build-fresh otel-push otel-user otel-clean otel-nuke

## otel-help: OTEL observability stack (arc-friday + collector + ClickHouse + ZooKeeper)
otel-help:
	@printf "\033[1mOTEL stack targets\033[0m\n\n"
	@grep -h "^## otel-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"

## otel-up: Start the full OTEL stack (telemetry + observability) and seed admin user
otel-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting OTEL stack...\n"
	$(COMPOSE_OTEL) up -d
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Waiting for arc-friday to become ready (first run: ~3-5 min)...\n"
	@until curl -sf http://localhost:3301/api/v1/health > /dev/null 2>&1; do \
	  printf "."; sleep 5; \
	done
	@printf "\n$(COLOR_OK)✓$(COLOR_OFF) arc-friday is ready\n"
	@$(MAKE) otel-user --no-print-directory

## otel-up-telemetry: Start the OTEL collector only (arc-friday-collector)
otel-up-telemetry:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-friday-collector...\n"
	$(COMPOSE_OTEL) up -d arc-friday-collector
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Collector started — OTLP on :4317 (gRPC) :4318 (HTTP), health on :13133\n"

## otel-up-observability: Start the observability backend only (arc-friday + ClickHouse + ZooKeeper)
otel-up-observability:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting observability backend...\n"
	$(COMPOSE_OTEL) up -d arc-friday-zookeeper arc-friday-clickhouse \
	  arc-friday-migrator-sync arc-friday-migrator-async arc-friday
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Waiting for arc-friday to become ready...\n"
	@until curl -sf http://localhost:3301/api/v1/health > /dev/null 2>&1; do \
	  printf "."; sleep 5; \
	done
	@printf "\n$(COLOR_OK)✓$(COLOR_OFF) arc-friday ready — http://localhost:3301\n"

## otel-down: Stop containers; data volumes are preserved
otel-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping OTEL stack...\n"
	$(COMPOSE_OTEL) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Stopped (volumes preserved — use otel-clean to remove data)\n"

## otel-health: Probe collector (:13133) and arc-friday (:3301) health endpoints
otel-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Collector health (:13133)... " && \
	  if curl -sf http://localhost:13133/ > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi
	@printf "$(COLOR_INFO)→$(COLOR_OFF) arc-friday       (:3301)...   " && \
	  if curl -sf http://localhost:3301/api/v1/health > /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## otel-logs: Stream logs from all OTEL containers
otel-logs:
	$(COMPOSE_OTEL) logs -f

## otel-ps: Show OTEL container status
otel-ps:
	$(COMPOSE_OTEL) ps

BUILD_FLAGS ?=

## otel-build: Build all 5 ARC otel images locally using cache (fast)
otel-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-friday-zookeeper...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REGISTRY)/$(ORG)/arc-friday-zookeeper:latest \
	  -f services/otel/observability/zookeeper.Dockerfile \
	  services/otel/observability/
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-friday-clickhouse...\n"
	@docker build $(BUILD_FLAGS) \
	  --build-arg TARGETARCH=$(shell uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') \
	  -t $(REGISTRY)/$(ORG)/arc-friday-clickhouse:latest \
	  -f services/otel/observability/clickhouse.Dockerfile \
	  services/otel/observability/
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-friday-migrator...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REGISTRY)/$(ORG)/arc-friday-migrator:latest \
	  -f services/otel/observability/migrator.Dockerfile \
	  services/otel/observability/
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-friday...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REGISTRY)/$(ORG)/arc-friday:latest \
	  -f services/otel/observability/Dockerfile \
	  services/otel/observability/
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-friday-collector...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REGISTRY)/$(ORG)/arc-friday-collector:latest \
	  -f services/otel/telemetry/Dockerfile \
	  services/otel/telemetry/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All 5 otel images built\n"

## otel-build-fresh: Build all 5 ARC otel images with --no-cache (clean rebuild)
otel-build-fresh: BUILD_FLAGS = --no-cache
otel-build-fresh: otel-build

## otel-push: Push locally built images to ghcr.io (requires: docker login ghcr.io)
otel-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing otel images to $(REGISTRY)/$(ORG)...\n"
	@for img in $(OTEL_IMAGES); do \
	  printf "$(COLOR_INFO)→$(COLOR_OFF) $$img\n"; \
	  docker push $$img || { printf "$(COLOR_ERR)✗ Push failed: $$img$(COLOR_OFF)\n"; exit 1; }; \
	done
	@printf "$(COLOR_OK)✓$(COLOR_OFF) All otel images pushed\n"

## otel-user: Create the default arc-friday admin user (idempotent — skips if already exists)
## Override defaults: make otel-user FRIDAY_EMAIL=you@example.com FRIDAY_PASSWORD=secret
otel-user:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Creating arc-friday admin user ($(FRIDAY_EMAIL))...\n"
	@curl -sf http://localhost:3301/api/v1/register \
	  -H "Content-Type: application/json" \
	  -d "{\"name\":\"$(FRIDAY_NAME)\",\"orgName\":\"$(FRIDAY_ORG)\",\"email\":\"$(FRIDAY_EMAIL)\",\"password\":\"$(FRIDAY_PASSWORD)\"}" \
	  | grep -q '"accessJwt"' \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) User created — login at http://localhost:3301\n" \
	  || printf "  User already exists or arc-friday not ready yet (run: make otel-health)\n"

## otel-clean: [DESTRUCTIVE] Remove containers, data volumes, and locally built images
otel-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: containers + data volumes (arc-friday-*) + local ARC images.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_OTEL) down --volumes --remove-orphans
	@for img in $(OTEL_IMAGES); do docker rmi $$img 2>/dev/null || true; done
	@printf "$(COLOR_OK)✓$(COLOR_OFF) otel environment cleaned\n"

## otel-nuke: [DESTRUCTIVE] Full reset — containers, volumes, images, and Docker network
otel-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL otel state: containers, volumes, images, and Docker network.\n"
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Data is unrecoverable. Full rebuild required after this.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_OTEL) down --volumes --remove-orphans
	@for img in $(OTEL_IMAGES); do docker rmi $$img 2>/dev/null || true; done
	@docker network rm arc_otel_net 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) otel reset complete — rebuild: make otel-build && make otel-up\n"
