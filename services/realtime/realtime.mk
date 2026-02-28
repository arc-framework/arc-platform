# ─── Daredevil / Sentry / Scribe: LiveKit Realtime Stack (arc-realtime) ──────
# Included by the root Makefile. All paths are relative to the repo root.
# Three services, one directory: arc-realtime + arc-realtime-ingress + arc-realtime-egress
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY ?= ghcr.io
ORG      ?= arc-framework

# BUILD_FLAGS, COLOR_* inherited from root Makefile
COMPOSE_REALTIME     := docker compose -f services/realtime/docker-compose.yml
REALTIME_IMAGE       := $(REGISTRY)/$(ORG)/arc-realtime
REALTIME_INGRESS_IMG := $(REGISTRY)/$(ORG)/arc-realtime-ingress
REALTIME_EGRESS_IMG  := $(REGISTRY)/$(ORG)/arc-realtime-egress

.PHONY: realtime-help \
        realtime-build realtime-build-fresh realtime-push realtime-publish realtime-tag \
        realtime-ingress-build realtime-ingress-build-fresh realtime-ingress-push realtime-ingress-publish \
        realtime-egress-build realtime-egress-build-fresh realtime-egress-push realtime-egress-publish \
        realtime-up realtime-down realtime-health realtime-logs realtime-clean realtime-nuke \
        realtime-ingress-up realtime-ingress-down realtime-ingress-health realtime-ingress-logs \
        realtime-egress-up realtime-egress-down realtime-egress-health realtime-egress-logs

## realtime-help: LiveKit realtime stack — Daredevil + Sentry + Scribe (arc-realtime)
realtime-help:
	@printf "\033[1mDaredevil / Sentry / Scribe targets\033[0m\n\n"
	@grep -h "^## realtime-" $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
	@printf "\n"
	@printf "  NOTE: UDP 50100-50200 must be open on host firewall for WebRTC media.\n"
	@printf "  NOTE: Set LIVEKIT_NODE_IP=<machine-ip> for non-local WebRTC clients.\n"
	@printf "  NOTE: Dev API keys are devkey/devsecret (static, dev-only).\n\n"

# ─── arc-realtime (Daredevil) ────────────────────────────────────────────────

## realtime-build: Build arc-realtime image locally using cache (fast)
realtime-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-realtime...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REALTIME_IMAGE):latest \
	  -f services/realtime/Dockerfile \
	  services/realtime/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(REALTIME_IMAGE):latest\n"

## realtime-build-fresh: Build arc-realtime with --no-cache (clean rebuild)
realtime-build-fresh: BUILD_FLAGS = --no-cache
realtime-build-fresh: realtime-build

## realtime-push: Push arc-realtime:latest to ghcr.io (requires: docker login ghcr.io)
realtime-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(REALTIME_IMAGE):latest...\n"
	@docker push $(REALTIME_IMAGE):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(REALTIME_IMAGE):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## realtime-publish: Build + push arc-realtime:latest to ghcr.io
realtime-publish: realtime-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-realtime/settings\n"

## realtime-tag: Tag arc-realtime:latest with a version (usage: make realtime-tag REALTIME_VERSION=realtime-v0.1.0)
realtime-tag:
	@[ -n "$(REALTIME_VERSION)" ] && [ "$(REALTIME_VERSION)" != "latest" ] \
	  || { printf "$(COLOR_ERR)✗ Set REALTIME_VERSION, e.g. make realtime-tag REALTIME_VERSION=realtime-v0.1.0$(COLOR_OFF)\n"; exit 1; }
	@docker tag $(REALTIME_IMAGE):latest $(REALTIME_IMAGE):$(REALTIME_VERSION) \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) $(REALTIME_IMAGE):latest → $(REALTIME_IMAGE):$(REALTIME_VERSION)\n" \
	  || { printf "$(COLOR_ERR)✗ Tag failed$(COLOR_OFF)\n"; exit 1; }

# ─── arc-realtime-ingress (Sentry) ───────────────────────────────────────────

## realtime-ingress-build: Build arc-realtime-ingress image locally using cache (fast)
realtime-ingress-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-realtime-ingress...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REALTIME_INGRESS_IMG):latest \
	  -f services/realtime/Dockerfile.ingress \
	  services/realtime/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(REALTIME_INGRESS_IMG):latest\n"

## realtime-ingress-build-fresh: Build arc-realtime-ingress with --no-cache
realtime-ingress-build-fresh: BUILD_FLAGS = --no-cache
realtime-ingress-build-fresh: realtime-ingress-build

## realtime-ingress-push: Push arc-realtime-ingress:latest to ghcr.io
realtime-ingress-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(REALTIME_INGRESS_IMG):latest...\n"
	@docker push $(REALTIME_INGRESS_IMG):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(REALTIME_INGRESS_IMG):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## realtime-ingress-publish: Build + push arc-realtime-ingress:latest to ghcr.io
realtime-ingress-publish: realtime-ingress-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-ingress pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-realtime-ingress/settings\n"

# ─── arc-realtime-egress (Scribe) ────────────────────────────────────────────

## realtime-egress-build: Build arc-realtime-egress image locally using cache (fast)
realtime-egress-build:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Building arc-realtime-egress...\n"
	@docker build $(BUILD_FLAGS) \
	  -t $(REALTIME_EGRESS_IMG):latest \
	  -f services/realtime/Dockerfile.egress \
	  services/realtime/
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Built → $(REALTIME_EGRESS_IMG):latest\n"

## realtime-egress-build-fresh: Build arc-realtime-egress with --no-cache
realtime-egress-build-fresh: BUILD_FLAGS = --no-cache
realtime-egress-build-fresh: realtime-egress-build

## realtime-egress-push: Push arc-realtime-egress:latest to ghcr.io
realtime-egress-push:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pushing $(REALTIME_EGRESS_IMG):latest...\n"
	@docker push $(REALTIME_EGRESS_IMG):latest \
	  && printf "$(COLOR_OK)✓$(COLOR_OFF) Pushed → $(REALTIME_EGRESS_IMG):latest\n" \
	  || { printf "$(COLOR_ERR)✗ Push failed — run: docker login ghcr.io$(COLOR_OFF)\n"; exit 1; }

## realtime-egress-publish: Build + push arc-realtime-egress:latest to ghcr.io
realtime-egress-publish: realtime-egress-push
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-egress pushed — set visibility at:\n"
	@printf "  https://github.com/orgs/$(ORG)/packages/container/arc-realtime-egress/settings\n"

# ─── Stack orchestration ─────────────────────────────────────────────────────

## realtime-up: Start all realtime services (Daredevil + Sentry + Scribe)
realtime-up:
	@docker network create arc_platform_net 2>/dev/null || true
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting realtime stack (arc-realtime + ingress + egress)...\n"
	$(COMPOSE_REALTIME) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Realtime stack started — LiveKit :7880, Ingress :7888, Egress :7889\n"

## realtime-down: Stop all realtime services
realtime-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping realtime stack...\n"
	$(COMPOSE_REALTIME) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Realtime stack stopped\n"

## realtime-health: Check health of all three realtime services
realtime-health:
	@failed=0; \
	 printf "$(COLOR_INFO)→$(COLOR_OFF) Daredevil health (:7880)... " && \
	   if curl -sf http://localhost:7880 -o /dev/null; then \
	     printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	   else \
	     printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; failed=1; \
	   fi; \
	 printf "$(COLOR_INFO)→$(COLOR_OFF) Sentry health (:7888)... " && \
	   if curl -sf http://localhost:7888 -o /dev/null; then \
	     printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	   else \
	     printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; failed=1; \
	   fi; \
	 printf "$(COLOR_INFO)→$(COLOR_OFF) Scribe health (:7889)... " && \
	   if curl -sf http://localhost:7889 -o /dev/null; then \
	     printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	   else \
	     printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; failed=1; \
	   fi; \
	 [ "$$failed" -eq 0 ] \
	   && printf "$(COLOR_OK)✓$(COLOR_OFF) All realtime services healthy\n" \
	   || { printf "$(COLOR_ERR)✗$(COLOR_OFF) $$failed realtime service(s) unhealthy\n"; exit 1; }

## realtime-logs: Stream logs from all three realtime services
realtime-logs:
	$(COMPOSE_REALTIME) logs -f

## realtime-clean: [DESTRUCTIVE] Remove all realtime containers
realtime-clean:
	@printf "$(COLOR_WARN)!$(COLOR_OFF) Removes: arc-realtime, arc-realtime-ingress, arc-realtime-egress containers.\n"
	@printf "  Active WebRTC rooms will be disconnected immediately.\n"
	@printf "  Type 'yes' to continue: " && read -r ans && [ "$$ans" = "yes" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_REALTIME) down --remove-orphans
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Realtime stack cleaned\n"

## realtime-nuke: [DESTRUCTIVE] Full reset — containers and local images
realtime-nuke:
	@printf "$(COLOR_ERR)!$(COLOR_OFF) Destroys ALL realtime state: containers and local images.\n"
	@printf "  Active WebRTC rooms will be disconnected immediately.\n"
	@printf "  Type 'nuke' to confirm: " && read -r ans && [ "$$ans" = "nuke" ] \
	  || { printf "  Aborted.\n"; exit 1; }
	$(COMPOSE_REALTIME) down --remove-orphans
	@docker rmi $(REALTIME_IMAGE):latest 2>/dev/null || true
	@docker rmi $(REALTIME_INGRESS_IMG):latest 2>/dev/null || true
	@docker rmi $(REALTIME_EGRESS_IMG):latest 2>/dev/null || true
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Realtime stack reset — rebuild: make realtime-build realtime-ingress-build realtime-egress-build\n"

# ─── Individual service targets ───────────────────────────────────────────────

## realtime-ingress-up: Start only the ingress service (requires arc-realtime healthy)
realtime-ingress-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-realtime-ingress...\n"
	$(COMPOSE_REALTIME) up -d arc-realtime-ingress
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-ingress started — RTMP :1935, controller :7888\n"

## realtime-ingress-down: Stop only the ingress service
realtime-ingress-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-realtime-ingress...\n"
	$(COMPOSE_REALTIME) stop arc-realtime-ingress
	$(COMPOSE_REALTIME) rm -f arc-realtime-ingress
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-ingress stopped\n"

## realtime-ingress-health: Probe arc-realtime-ingress health endpoint (:7888)
realtime-ingress-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Sentry health (:7888)... " && \
	  if curl -sf http://localhost:7888 -o /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## realtime-ingress-logs: Stream arc-realtime-ingress logs
realtime-ingress-logs:
	$(COMPOSE_REALTIME) logs -f arc-realtime-ingress

## realtime-egress-up: Start only the egress service (requires arc-realtime healthy)
realtime-egress-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting arc-realtime-egress...\n"
	$(COMPOSE_REALTIME) up -d arc-realtime-egress
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-egress started — controller :7889\n"

## realtime-egress-down: Stop only the egress service
realtime-egress-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping arc-realtime-egress...\n"
	$(COMPOSE_REALTIME) stop arc-realtime-egress
	$(COMPOSE_REALTIME) rm -f arc-realtime-egress
	@printf "$(COLOR_OK)✓$(COLOR_OFF) arc-realtime-egress stopped\n"

## realtime-egress-health: Probe arc-realtime-egress health endpoint (:7889)
realtime-egress-health:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Scribe health (:7889)... " && \
	  if curl -sf http://localhost:7889 -o /dev/null; then \
	    printf "$(COLOR_OK)✓$(COLOR_OFF)\n"; \
	  else \
	    printf "$(COLOR_ERR)✗ FAILED$(COLOR_OFF)\n"; exit 1; \
	  fi

## realtime-egress-logs: Stream arc-realtime-egress logs
realtime-egress-logs:
	$(COMPOSE_REALTIME) logs -f arc-realtime-egress
