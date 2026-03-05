# Feature: nervous-system

> Spec folder will be: `specs/NNN-nervous-system/`
> HLD: `docs/ard/NERVOUS-SYSTEM-HLD.md`

## Concept

NATS and Pulsar together form the platform's "nervous system" — the connective tissue through which agents communicate, data pre-positions, and inference results flow reactively. The primary outcome is reducing TTFT (Time to First Token) from ~3-5s to sub-200ms at P50.

```
NATS    = fast nerves    — real-time impulse delivery, ephemeral, request-reply
Pulsar  = spinal cord    — durable pathways, fan-out, replay, backpressure
Redis   = muscle memory  — cached context, hot state
```

## Role in the Broader ARC Infrastructure

The nervous system is the **foundation layer** of ARC as AI infrastructure. Every higher-level capability depends on it:

- Speed goal (sub-200ms TTFT) is only achievable with NATS token streaming (Phase 1)
- The Resource + Event pattern (REST mutation → Pulsar topic) requires Phase 3 Pulsar fan-out
- The accuracy loop (arc-guard (RoboCop / Guardrails), arc-critic (Gordon Ramsay / Critic), arc-gym (Ivan Drago / Trainer)) subscribes to Pulsar topics produced in Phase 3
- Voice (arc-voice-agent (Scarlett / Voice)) consumes inference streams from Pulsar

Phase 3 completion unlocks the full ARC infrastructure vision. Phases 1 and 2 are Sherlock-internal; Phase 3 is the platform-wide event backbone.

## Current Bottleneck Chain

Every request today flows sequentially:

```
Request arrives (NATS)
  → embed query (CPU SentenceTransformer, ~100ms, BLOCKS)
  → DB vector search (Postgres HNSW, ~50ms, BLOCKS)
  → build prompt + inject context
  → LLM.ainvoke()  ← waits for ALL prior steps
  → full response buffered in memory
  → NATS reply sent (single blob)

TTFT = sum of ALL steps. First token only when last byte is ready.
```

The NATS handlers (`nats_handler.py`, `openai_nats_handler.py`) use `invoke_graph()` which buffers the full response. The streaming path (`stream_graph()`) already exists in `graph.py` but is only wired to HTTP/SSE — not NATS or Pulsar.

## Architecture

```
                     ┌───────────────────────────────────────┐
Client               │           NERVOUS SYSTEM               │
  │                  │                                         │
  │──NATS request──▶ │  reasoner.request                       │
  │                  │    ├── spawn: embed query (threadpool)  │
  │                  │    ├── spawn: fetch context (Redis)     │
  │◀─ token chunk 1 ─│    └── begin LLM stream immediately     │
  │◀─ token chunk 2 ─│         inject retrieval when ready ──▶│──▶ Pulsar: reasoner-inference-{id}
  │◀─ token chunk 3 ─│                                         │
  │                  │  Pulsar subscriptions (fan-out):        │
  │                  │    reasoner-requests  → durable async   │
  │                  │    reasoner-results   → downstream subs │
  └──────────────────└─────────────────────────────────────── ┘
```

## Phased Implementation

### Phase 1 — Quick Wins (highest TTFT impact, no infra changes)

**1. Token streaming over NATS**
- Biggest single TTFT improvement: 3-5s → ~200ms
- `nats_handler.py` and `openai_nats_handler.py` call `invoke_graph()` (buffers full response)
- Replace with `stream_graph()` and publish token chunks to `reasoner.stream.{request_id}`
- `stream_graph()` in `graph.py` already works — just unwired from NATS
- Client subscribes to `reasoner.stream.{request_id}` for chunks, `reasoner.v1.result` for completion signal

**2. CPU embedding off critical path**
- `memory.py:92` — `SentenceTransformer.encode()` runs synchronously, blocking for ~100ms
- Wrap in `asyncio.run_in_executor()` with a dedicated `ThreadPoolExecutor(max_workers=2)`
- No graph changes needed

**3. TTFT baseline metrics**
- `observability.py` — add `ttft_seconds` histogram
- Measure time from request receive → first token emitted (not full response complete)
- Establishes baseline before further optimizations

### Phase 2 — Parallel Pipeline

**4. Parallel retrieve + LLM start**
- `graph.py:185` `invoke_graph` runs `retrieve_context` → `generate_response` sequentially
- Restructure: start LLM with empty/partial context, inject retrieval results as they arrive via LangGraph state
- Removes ~150ms retrieval latency from critical path

**5. Redis context cache (Sonic)**
- Sonic is already in the platform — wire it in as a cache layer
- Cache key: `(user_id, query_embedding_hash)` → `context_chunks`, TTL ~5min
- `memory.py` checks cache first, falls back to Postgres HNSW on miss
- First request populates cache; repeated questions from same user get sub-10ms retrieval

### Phase 3 — Pulsar Durable Fan-out

**6. Enable Pulsar as event backbone**
- Pulsar already deployed in `reason` profile, disabled by default (`SHERLOCK_PULSAR_ENABLED=false`)
- Each inference publishes token-level events to `reasoner-inference-{id}` topic
- Multiple downstream subscribers (voice pipeline, logging, analytics) consume independently without blocking LLM
- `pulsar_handler.py:79-134` `_process` method → replace with streaming publish variant

**7. NATS → Pulsar graceful degradation**
- Under load: NATS request-reply with 500ms timeout
- If timeout: queue to Pulsar `reasoner-requests` for durable async processing
- Result delivered to original caller via correlation ID when ready
- Prevents overload from cascading into dropped requests

## TTFT Improvement Estimates

| Phase | Optimization | Latency Saved | Complexity |
|-------|-------------|---------------|------------|
| 1 | Streaming over NATS | 1.9-4.9s | Medium |
| 1 | Embedding off critical path | 100ms | Low |
| 2 | Parallel retrieve + generate | 150-300ms | Medium |
| 2 | Redis context cache | 200-400ms (cache hits) | Medium |
| 3 | Pulsar token fan-out | Throughput scale-out | High |
| 3 | NATS/Pulsar fallback | P95 improvement | Low |

**Target:** P50 TTFT < 200ms (from current ~3-5s)

## Key Files

```
services/reasoner/src/reasoner/graph.py             # invoke_graph, stream_graph, node definitions
services/reasoner/src/reasoner/streaming.py         # GraphStreamingAdapter — reuse for NATS
services/reasoner/src/reasoner/nats_handler.py      # replace invoke_graph → stream_graph
services/reasoner/src/reasoner/openai_nats_handler.py
services/reasoner/src/reasoner/pulsar_handler.py    # add token-level publish + Resource+Event topics
services/reasoner/src/reasoner/memory.py            # embedding threadpool + Redis cache layer
services/reasoner/src/reasoner/observability.py     # add ttft_seconds histogram
services/reasoner/src/reasoner/config.py            # NATS subjects, Pulsar topics, Redis URL
services/reasoner/contracts/asyncapi.yaml           # add stream subject + Pulsar topic definitions
services/messaging/service.yaml                     # arc-pulse (Flash / NATS) — already deployed
services/cache/service.yaml                         # arc-db-cache (Sonic / Redis) — already deployed
services/streaming/service.yaml                     # arc-stream (Dr. Strange / Pulsar) — reason profile
```

## Dependencies

- `decouple-service-codenames` must land first — in progress on current branch
- arc-db-cache (Sonic / Redis) must be verified healthy in `think` profile before Phase 2 cache work
- arc-stream (Dr. Strange / Pulsar) must be verified healthy in `reason` profile before Phase 3

## Decisions (resolved)

1. NATS token streaming uses dedicated subject `reasoner.stream.{request_id}` — not reply-to inbox. Cleaner fan-out, client subscribes explicitly.
2. Redis cache invalidation: TTL-based (5min default) + explicit invalidation when conversation history changes (new message appended resets key).
3. Voice pipeline (arc-voice-agent (Scarlett / Voice)) consumes from Pulsar (durable, async) — not NATS. NATS is for real-time client streaming only.
4. `stream_graph()` is the default path for all transports. Buffering (`invoke_graph`) is opt-in only.
