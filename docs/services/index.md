# Service Map

The ARC Platform composes services into profiles — **think**, **reason**, and **ultra-instinct** — each building on the previous tier. Start with `think` for core infrastructure, add `reason` for AI capabilities, and `ultra-instinct` for the full platform (coming soon).

| Service | Codename | Port(s) | Description |
|---------|----------|---------|-------------|
| [gateway](./gateway.md) | Heimdall | 80, 8090 | API gateway — routes all inbound HTTP traffic (Traefik) |
| [messaging](./messaging.md) | Flash | 4222, 8222 | Ephemeral message broker for agent-to-agent communication (NATS) |
| [streaming](./streaming.md) | Dr. Strange | 6650, 8082 | Durable event streaming with replay (Apache Pulsar) |
| [cache](./cache.md) | Sonic | 6379 | Sub-millisecond key-value cache for sessions and rate limits (Redis) |
| [persistence](./sql-db.md) | Oracle | 5432 | Relational long-term memory with vector search (PostgreSQL + pgvector) |
| cortex | Cortex | 8801 | Platform bootstrap service — workspace init and health orchestration |
| [friday-collector](./friday.md) | Friday Collector | 4317 | OTEL collector — receives traces and metrics from all services |
| [reasoner](./reasoner.md) | Sherlock | 8802 | LLM reasoning engine with RAG and streaming (LangGraph) |
| [otel](./friday.md) | Friday | 3301, 8080 | Observability UI — traces, metrics, dashboards (SigNoz + ClickHouse) |
| [realtime](./realtime.md) | Daredevil | 7880–7882 | WebRTC media routing for low-latency voice and video (LiveKit) |
| [vault](./vault.md) | Nick Fury | 8200 | Secrets manager — dynamic secrets and encryption-as-a-service (OpenBao) |
| [flags](./flags.md) | Mystique | 4242 | Feature flags with OpenFeature compatibility (Unleash) |
| [storage](./storage.md) | Tardis | 9000, 9001 | S3-compatible object storage for artifacts and model weights (MinIO) |
| [voice](./voice.md) | Scarlett | 8803 | Voice agent — STT, LLM, TTS pipeline with WebRTC support |

## Profiles

| Profile | Services | Use case |
|---------|----------|----------|
| `think` | gateway, messaging, streaming, cache, persistence, cortex, friday-collector | Core infrastructure — minimal footprint |
| `reason` | think + reasoner + voice + *growing* | AI development — reasoning and voice, more services being added |
| `ultra-instinct` | *Coming soon* | Full platform with all capabilities |
