# Service Map

The ARC Platform composes services into three profiles — **think**, **reason**, and **ultra-instinct** — each building on the previous tier. Every service in a lower tier is included in the tiers above it. Capability-gated services (observe, security, storage, voice) are only active when the corresponding capability is declared in `arc.yaml`.

| Service | Codename | Port(s) | Health URL | Profile(s) |
|---------|----------|---------|------------|------------|
| [gateway](./gateway.md) | Heimdall | 80, 8090 | `http://localhost:8090/health` | think, reason, ultra-instinct |
| [messaging](./messaging.md) | Flash | 4222, 8222 | `http://localhost:8222/health` | think, reason, ultra-instinct |
| [streaming](./streaming.md) | Dr. Strange | 6650, 8082 | `http://localhost:8082/health` | think, reason, ultra-instinct |
| [cache](./cache.md) | Sonic | 6379 | `http://localhost:6379/health` (ping) | think, reason, ultra-instinct |
| [persistence](./sql-db.md) | Oracle | 5432 | `http://localhost:5432/health` | think, reason, ultra-instinct |
| cortex | Cortex | 8801 | `http://localhost:8801/health` | think, reason, ultra-instinct |
| [friday-collector](./friday) | Friday Collector | 4317 | `http://localhost:13133/health` | think, reason, ultra-instinct |
| [reasoner](./reasoner.md) | Sherlock | 8802 | `http://localhost:8802/health` | reason, ultra-instinct |
| [otel](./friday.md) | Friday | 3301, 8080 | `http://localhost:3301/health` | ultra-instinct (observe) |
| [realtime](./realtime.md) | Daredevil | 7880, 7881, 7882 | `http://localhost:7880/health` | ultra-instinct |
| [vault](./vault.md) | Nick Fury | 8200 | `http://localhost:8200/health` | ultra-instinct (security) |
| [flags](./flags.md) | Mystique | 4242 | `http://localhost:4242/health` | ultra-instinct (security) |
| [storage](./storage.md) | Tardis | 9000, 9001 | `http://localhost:9000/health` | ultra-instinct (storage) |
| [voice](./voice.md) | Scarlett | 8803 | `http://localhost:8803/health` | ultra-instinct (voice) |

## Profiles

| Profile | Services | Use case |
|---------|----------|----------|
| `think` | gateway, messaging, streaming, cache, persistence, cortex, friday-collector | Core reasoning — minimal footprint |
| `reason` | think + reasoner | LLM inference via Sherlock |
| `ultra-instinct` | reason + realtime + otel + vault + flags + storage + voice | Full platform with all capabilities |

Capability-gated services are toggled via the `capabilities` field in `arc.yaml`:

```yaml
tier: ultra-instinct
capabilities:
  - observe    # activates arc-friday (SigNoz)
  - security   # activates arc-vault + arc-flags
  - storage    # activates arc-storage (MinIO)
  - voice      # activates arc-voice-agent (Scarlett)
```
