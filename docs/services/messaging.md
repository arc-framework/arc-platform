---
url: /arc-platform/docs/services/messaging.md
---
# Messaging (Flash)

> **Status:** Active | **Port:** 4222, 8222 | **Profile:** think, reason, ultra-instinct

The `arc-messaging` service (Flash) is the platform message broker built on NATS. It carries low-latency, ephemeral messages between platform services and agent workers — **the fast synchronous layer** of the A.R.C. messaging system.

For durable event streaming with persistence and replay, see [Streaming (Dr. Strange)](/services/streaming).

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-messaging:latest` |
| Port(s) | 4222 (client), 8222 (monitoring) |
| Health | `http://localhost:8222/healthz` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make messaging-up` | Start the service |
| `make messaging-down` | Stop the service |
| `make messaging-health` | Check health |
| `make messaging-logs` | Tail service logs |

## When to Use Messaging (Flash)

Messaging (Flash) is ideal for **synchronous, ephemeral** communication:

| Use Case | Messaging (Flash) | Streaming (Dr. Strange) |
|----------|------------------|------------------------|
| Agent asks another agent to act | ✅ | ❌ |
| Distribute work across workers | ✅ (queue groups) | ❌ |
| Request/reply pattern | ✅ | ❌ |
| Heartbeat / presence | ✅ | ❌ |
| Event sourcing / audit log | ❌ | ✅ |
| Replay historical events | ❌ | ✅ |
| Cross-service event distribution | ❌ | ✅ |

**Rule of thumb:** If you need the other side to respond now, use `arc-messaging`. If you need a durable record that can be replayed later, use `arc-streaming`.

## Features

* **Sub-millisecond latency** — in-memory only, no disk I/O
* **Pub/sub** — fan-out to multiple subscribers
* **Request/reply** — synchronous RPC over messaging
* **Queue groups** — load-balanced work distribution
* **Lightweight** — minimal CPU and RAM footprint

## Connection

```bash
# Default client URL
nats://localhost:4222

# Monitoring dashboard
open http://localhost:8222
```

## Patterns

### Pub/Sub (Fan-out)

```
Publisher → Topic → Subscriber A
                  → Subscriber B
                  → Subscriber C
```

### Request/Reply (RPC)

```
Agent A → request(topic, payload) → Agent B
Agent A ←    reply(result)        ←
```

### Queue Group (Load Balancing)

```
Job Queue → Worker 1
          → Worker 2 (only one receives each message)
          → Worker 3
```

## Reasoner Integration

The Reasoner service (Sherlock) uses `arc-messaging` (Flash) as its primary async trigger. See [Reasoner](/services/reasoner) for the full NATS subject schema used by the platform.
