---
url: /arc-platform/docs/services/streaming.md
---
# Streaming (Dr. Strange)

> **Status:** Active | **Port:** 6650, 8082 | **Profile:** think, reason, ultra-instinct

The `arc-streaming` service (Dr. Strange) is the platform event streaming service built on Apache Pulsar. It provides durable, ordered, multi-consumer topic streams — **the persistent event layer** of the A.R.C. messaging system. Events can be replayed from any point in time.

For low-latency ephemeral messaging, see [Messaging (Flash)](/services/messaging).

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-streaming:latest` |
| Port(s) | 6650 (broker), 8082 (admin HTTP) |
| Health | `http://localhost:8082/admin/v2/brokers/health` |
| Metrics | `http://localhost:8082/metrics` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make streaming-up` | Start the service |
| `make streaming-down` | Stop the service |
| `make streaming-health` | Check health |
| `make streaming-logs` | Tail service logs |

## When to Use Streaming (Dr. Strange)

Streaming (Dr. Strange) handles **durable, replayable** event streams:

| Use Case | Streaming (Dr. Strange) | Messaging (Flash) |
|----------|------------------------|------------------|
| Event sourcing / CQRS | ✅ | ❌ |
| Audit logs and compliance | ✅ | ❌ |
| Replay historical events | ✅ | ❌ |
| Cross-service event distribution | ✅ | ❌ |
| Data pipelines / ETL | ✅ | ❌ |
| Low-latency agent RPC | ❌ | ✅ |
| Request/reply patterns | ❌ | ✅ |

## Topic Hierarchy

```
Tenant (arc)
  └── Namespace (agents)
      └── Topic (inference.completed)
          └── Partitions (0, 1, 2, ...)
```

## Platform Events

The Reasoner (Sherlock) publishes these Pulsar topics:

| Topic | Description |
|-------|-------------|
| `arc.request.received` | Inference request accepted |
| `arc.inference.completed` | Inference finished with token usage |
| `arc.billing.usage` | Aggregated usage for billing |

## Admin CLI

```bash
# Access Pulsar admin CLI inside container
docker compose exec arc-streaming bin/pulsar-admin

# List namespaces
docker compose exec arc-streaming bin/pulsar-admin namespaces list arc

# Create namespace
docker compose exec arc-streaming bin/pulsar-admin namespaces create arc/agents

# List topics
docker compose exec arc-streaming bin/pulsar-admin topics list arc/agents

# Check topic backlog
docker compose exec arc-streaming bin/pulsar-admin topics stats arc/agents/inference.completed
```

## Client Libraries

| Language | Package |
|----------|---------|
| Go | `github.com/apache/pulsar-client-go/pulsar` |
| Python | `pulsar-client` |
| Java | `pulsar-client` |

### Go Example

```go
import "github.com/apache/pulsar-client-go/pulsar"

client, _ := pulsar.NewClient(pulsar.ClientOptions{
    URL: "pulsar://localhost:6650",
})
defer client.Close()

// Producer
producer, _ := client.CreateProducer(pulsar.ProducerOptions{
    Topic: "arc/agents/inference.completed",
})
producer.Send(context.Background(), &pulsar.ProducerMessage{
    Payload: []byte(`{"request_id":"abc","tokens":512}`),
})

// Consumer with replay from earliest
consumer, _ := client.Subscribe(pulsar.ConsumerOptions{
    Topic:            "arc/agents/inference.completed",
    SubscriptionName: "billing-service",
    SubscriptionInitialPosition: pulsar.SubscriptionPositionEarliest,
})
msg, _ := consumer.Receive(context.Background())
consumer.Ack(msg)
```

## Message Replay

```bash
# Replay from earliest message on a subscription
docker compose exec arc-streaming bin/pulsar-client consume \
  --subscription-position Earliest arc/agents/inference.completed

# Seek to specific timestamp (ISO 8601)
docker compose exec arc-streaming bin/pulsar-admin topics \
  reset-cursor arc/agents/inference.completed \
  --subscription billing-service \
  --time "2026-01-01T00:00:00Z"
```

## Production Notes

* **Tiered storage** — offload old data to MinIO (Tardis) for long-term retention
* **Monitor backlog** — growing subscription backlog indicates a consumer is behind
* **Resource usage** — Pulsar is heavier than NATS; ensure 2+ GB RAM for the broker
