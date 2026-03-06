# ─── Dev Tools (lightweight broker + data clients) ──────────────────────────
# Included by the root Makefile. Optional local-only tooling for debugging.
#
# Broker URLs (container-side):
#   NATS           nats://arc-messaging:4222    monitor http://localhost:8222
#   Pulsar         pulsar://arc-streaming:6650  admin   http://arc-streaming:8080
#
# Data UIs (host-side):
#   Adminer        http://localhost:8085        PostgreSQL / arc-persistence
#   Redis Commander http://localhost:8086       Redis / arc-cache
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE_DEV_TOOLS  := docker compose -f dev-tools/docker-compose.yml
NATS_SERVER        := nats://arc-messaging:4222
PULSAR_ADMIN_URL   := http://arc-streaming:8080
PULSAR_CLIENT_URL  := pulsar://arc-streaming:6650
PULSAR_TENANT      ?= arc
PULSAR_NS          ?= default
PULSAR_TOPIC       ?= persistent://arc/default/reasoner-requests
PULSAR_SUB         ?= arc-dev-inspector

# Internal helpers — not exposed to the user
_NATS  := docker exec arc-dev-nats nats -s $(NATS_SERVER)
_PADM  := docker exec arc-dev-pulsar /pulsar/bin/pulsar-admin --admin-url $(PULSAR_ADMIN_URL)
_PCLI  := docker exec arc-dev-pulsar /pulsar/bin/pulsar-client --url $(PULSAR_CLIENT_URL)

.PHONY: \
  dev-tools-help dev-tools-up dev-tools-down dev-tools-logs dev-tools-ps \
  dev-tools-shell-nats dev-tools-shell-pulsar \
  nats-info nats-streams nats-consumers nats-sub nats-pub nats-ping \
  pulsar-brokers pulsar-tenants pulsar-namespaces pulsar-topics \
  pulsar-topic-stats pulsar-consumers pulsar-consume pulsar-produce \
  dev-tools-redis dev-tools-postgres

## dev-tools-help: Broker inspection + data UIs — run 'make dev-tools-help' for full list
dev-tools-help:
	@printf "\033[1mDev Tools\033[0m\n\n"
	@printf "  \033[1mLifecycle\033[0m\n"
	@printf "    make dev-tools-up              Start all dev-tools containers\n"
	@printf "    make dev-tools-down            Stop all dev-tools containers\n"
	@printf "    make dev-tools-ps              Show container status\n"
	@printf "    make dev-tools-logs            Tail all dev-tools logs\n\n"
	@printf "  \033[1mNATS (arc-messaging)\033[0m\n"
	@printf "    make nats-info                 Server info + connection stats\n"
	@printf "    make nats-streams              List JetStream streams\n"
	@printf "    make nats-consumers            List consumers on a stream (STREAM=<name>)\n"
	@printf "    make nats-sub                  Subscribe to all arc.* subjects (live tail)\n"
	@printf "    make nats-pub                  Publish a test message (SUBJ=<subj> MSG=<text>)\n"
	@printf "    make nats-ping                 Ping arc-messaging broker\n"
	@printf "    make dev-tools-shell-nats      Open interactive nats-box shell\n\n"
	@printf "  \033[1mPulsar (arc-streaming)\033[0m\n"
	@printf "    make pulsar-brokers            List active brokers\n"
	@printf "    make pulsar-tenants            List tenants\n"
	@printf "    make pulsar-namespaces         List namespaces in tenant (PULSAR_TENANT=arc)\n"
	@printf "    make pulsar-topics             List topics in namespace (PULSAR_NS=default)\n"
	@printf "    make pulsar-topic-stats        Show stats for topic (PULSAR_TOPIC=...)\n"
	@printf "    make pulsar-consumers          Show subscriptions/consumers for topic\n"
	@printf "    make pulsar-consume            Tail messages from topic (PULSAR_TOPIC=...)\n"
	@printf "    make pulsar-produce            Publish a test message to topic\n"
	@printf "    make dev-tools-shell-pulsar    Open interactive pulsar shell\n\n"
	@printf "  \033[1mData UIs\033[0m\n"
	@printf "    make dev-tools-redis           Print Redis Commander URL\n"
	@printf "    make dev-tools-postgres        Print Adminer connection settings\n"
	@printf "\n  \033[1mURLs\033[0m\n"
	@printf "    Adminer (Postgres):    http://localhost:8085\n"
	@printf "    Redis Commander:       http://localhost:8086\n"
	@printf "    NATS Monitor:          http://localhost:8222\n\n"

# ─── Lifecycle ────────────────────────────────────────────────────────────────

## dev-tools-up: Start all dev-tools containers
dev-tools-up:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Starting dev tools...\n"
	$(COMPOSE_DEV_TOOLS) up -d
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Dev tools started\n"
	@printf "    Adminer:          http://localhost:8085\n"
	@printf "    Redis Commander:  http://localhost:8086\n"
	@printf "    NATS Monitor:     http://localhost:8222\n"

## dev-tools-down: Stop all dev-tools containers
dev-tools-down:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stopping dev tools...\n"
	$(COMPOSE_DEV_TOOLS) down
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Dev tools stopped\n"

## dev-tools-logs: Tail logs from all dev-tools containers
dev-tools-logs:
	$(COMPOSE_DEV_TOOLS) logs -f

## dev-tools-ps: Show dev-tools container status
dev-tools-ps:
	$(COMPOSE_DEV_TOOLS) ps

# ─── NATS ─────────────────────────────────────────────────────────────────────

## nats-info: Show arc-messaging server info, connections, and JetStream status
nats-info:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) NATS server info (/varz)...\n"
	@docker exec arc-dev-nats sh -c 'wget -qO- http://arc-messaging:8222/varz | head -60'
	@printf "\n$(COLOR_INFO)→$(COLOR_OFF) Active connections (/connz)...\n"
	@docker exec arc-dev-nats sh -c 'wget -qO- http://arc-messaging:8222/connz'
	@printf "\n$(COLOR_INFO)→$(COLOR_OFF) Subscriptions (/subsz)...\n"
	@docker exec arc-dev-nats sh -c 'wget -qO- http://arc-messaging:8222/subsz'
	@printf "\n$(COLOR_INFO)→$(COLOR_OFF) JetStream account summary...\n"
	$(_NATS) account info 2>/dev/null || printf "$(COLOR_WARN)!$(COLOR_OFF) JetStream not configured on this server\n"

## nats-streams: List all JetStream streams on arc-messaging
nats-streams:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) JetStream streams on arc-messaging...\n"
	$(_NATS) stream ls 2>/dev/null || printf "$(COLOR_WARN)!$(COLOR_OFF) No streams found (JetStream may not be configured)\n"

## nats-consumers: List consumers for a JetStream stream (usage: make nats-consumers STREAM=<name>)
nats-consumers:
	@[ -n "$(STREAM)" ] \
	  || { printf "$(COLOR_ERR)✗$(COLOR_OFF) Set STREAM=<stream-name>  e.g: make nats-consumers STREAM=EVENTS\n"; exit 1; }
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Consumers for stream '$(STREAM)'...\n"
	$(_NATS) consumer ls $(STREAM)

## nats-sub: Live-tail all arc.* subjects (Ctrl-C to stop)
nats-sub:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Subscribing to 'arc.>' on arc-messaging — Ctrl-C to stop\n"
	$(_NATS) subscribe 'arc.>'

## nats-pub: Publish a test message to a NATS subject (usage: make nats-pub SUBJ=arc.reasoner.request MSG='{"user_id":"dev","text":"hello"}')
nats-pub:
	@[ -n "$(SUBJ)" ] && [ -n "$(MSG)" ] \
	  || { printf "$(COLOR_ERR)✗$(COLOR_OFF) Set SUBJ and MSG  e.g: make nats-pub SUBJ=arc.reasoner.request MSG='{\"user_id\":\"dev\",\"text\":\"hello\"}'\n"; exit 1; }
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Publishing to '$(SUBJ)'...\n"
	$(_NATS) publish '$(SUBJ)' '$(MSG)'
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Published\n"

## nats-ping: Ping the arc-messaging NATS broker
nats-ping:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pinging arc-messaging...\n"
	$(_NATS) rtt

# ─── Shells ───────────────────────────────────────────────────────────────────

## dev-tools-shell-nats: Open an interactive nats-box shell with NATS_URL pre-set
dev-tools-shell-nats:
	@docker exec -it -e NATS_URL=$(NATS_SERVER) arc-dev-nats sh

## dev-tools-shell-pulsar: Open an interactive shell inside the Pulsar container
dev-tools-shell-pulsar:
	@docker exec -it arc-dev-pulsar sh

# ─── Pulsar ───────────────────────────────────────────────────────────────────

## pulsar-brokers: List active Pulsar brokers
pulsar-brokers:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Active Pulsar brokers...\n"
	$(_PADM) brokers list standalone

## pulsar-tenants: List all Pulsar tenants
pulsar-tenants:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Pulsar tenants...\n"
	$(_PADM) tenants list

## pulsar-namespaces: List namespaces in tenant (defaults to PULSAR_TENANT=arc)
pulsar-namespaces:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Namespaces in tenant '$(PULSAR_TENANT)'...\n"
	$(_PADM) namespaces list $(PULSAR_TENANT) 2>/dev/null \
	  || printf "$(COLOR_WARN)!$(COLOR_OFF) Tenant '$(PULSAR_TENANT)' does not exist yet.\n"\
" Pulsar tenant 'arc' is created when arc-reasoner starts with SHERLOCK_PULSAR_ENABLED=true\n"\
" Available tenants: run 'make pulsar-tenants'\n"

## pulsar-topics: List all topics in namespace (defaults to arc/default)
pulsar-topics:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Topics in '$(PULSAR_TENANT)/$(PULSAR_NS)'...\n"
	$(_PADM) topics list $(PULSAR_TENANT)/$(PULSAR_NS) 2>/dev/null \
	  || printf "$(COLOR_WARN)!$(COLOR_OFF) Namespace '$(PULSAR_TENANT)/$(PULSAR_NS)' not found.\n"\
" Topics are created when arc-reasoner starts with SHERLOCK_PULSAR_ENABLED=true.\n"\
" Try: make pulsar-tenants → make pulsar-namespaces PULSAR_TENANT=public\n"

## pulsar-topic-stats: Show detailed stats for a topic (usage: make pulsar-topic-stats PULSAR_TOPIC=persistent://arc/default/reasoner-requests)
pulsar-topic-stats:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Stats for '$(PULSAR_TOPIC)'...\n"
	$(_PADM) topics stats $(PULSAR_TOPIC)

## pulsar-consumers: List subscriptions and consumers for a topic
pulsar-consumers:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Subscriptions on '$(PULSAR_TOPIC)'...\n"
	$(_PADM) topics stats $(PULSAR_TOPIC) | grep -A 30 '"subscriptions"' || true

## pulsar-consume: Tail messages from a Pulsar topic (usage: make pulsar-consume PULSAR_TOPIC=persistent://arc/default/reasoner-results)
pulsar-consume:
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Consuming from '$(PULSAR_TOPIC)' (subscription: $(PULSAR_SUB)) — Ctrl-C to stop\n"
	$(_PCLI) consume \
	  -s $(PULSAR_SUB) \
	  -n 0 \
	  -p Earliest \
	  $(PULSAR_TOPIC)

## pulsar-produce: Publish a test message to a Pulsar topic (usage: make pulsar-produce PULSAR_TOPIC=... MSG='hello')
pulsar-produce:
	@[ -n "$(MSG)" ] \
	  || { printf "$(COLOR_ERR)✗$(COLOR_OFF) Set MSG  e.g: make pulsar-produce PULSAR_TOPIC=persistent://arc/default/reasoner-requests MSG='test'\n"; exit 1; }
	@printf "$(COLOR_INFO)→$(COLOR_OFF) Producing to '$(PULSAR_TOPIC)'...\n"
	$(_PCLI) produce -m '$(MSG)' $(PULSAR_TOPIC)
	@printf "$(COLOR_OK)✓$(COLOR_OFF) Produced\n"

# ─── Data UIs ─────────────────────────────────────────────────────────────────

## dev-tools-redis: Print Redis Commander URL
dev-tools-redis:
	@printf "Redis Commander: http://localhost:8086\n"
	@printf "Target:          arc-cache:6379\n"

## dev-tools-postgres: Print Adminer connection settings for arc-persistence
dev-tools-postgres:
	@printf "Adminer:   http://localhost:8085\n"
	@printf "System:    PostgreSQL\n"
	@printf "Server:    arc-persistence\n"
	@printf "Username:  arc\n"
	@printf "Password:  arc\n"
	@printf "Database:  arc\n"
