# Why A.R.C.?

## The Problem

Building a production AI agent platform today means weeks of infrastructure work before you write a single line of agent logic. Teams cobble together API gateways, secrets managers, message brokers, vector databases, and observability stacks — only to discover that none of them talk to each other out of the box. The result is fragile, hand-wired plumbing that breaks under pressure and resists change.

Vendor lock-in compounds the problem. Many "open-source" AI platforms ship under restrictive licenses (BSL, source-available, non-compete clauses) that limit how you deploy and scale. When you need to swap a component, you discover your architecture is welded to a single vendor's SDK. Meanwhile, observability and resilience testing remain afterthoughts, bolted on months later when production incidents force the issue.

A.R.C. was built to fix this: a platform that ships production-ready infrastructure on day one, stays genuinely open-source, and treats every service as swappable.

## Traditional vs. The A.R.C. Way

| Traditional | The A.R.C. Way |
|-------------|----------------|
| Days spent wiring infrastructure | `arc run --profile think` — done |
| Manual service integration | Pre-integrated: Heimdall, Flash, Sherlock, Scarlett, and more |
| Risk of vendor lock-in | 100% open-source, open standards |
| Painful observability setup | OTEL + Friday Collector in every profile |
| Scaling bottlenecks | Event-driven, horizontally scalable |
| Steep learning curves | Production-ready in minutes |
| Unknown resilience | Health checks and structured runbook from day one |

## Eight Reasons Teams Choose A.R.C.

### 1. Minutes, Not Months

One command deploys the full platform. `arc run --profile think` handles what takes teams weeks to configure manually: gateway routing, database provisioning, message broker wiring, OTEL collection, and service discovery. Your platform is running before your coffee gets cold.

### 2. 100% FOSS

Every service in the A.R.C. stack ships under Apache 2.0, MIT, or MPL. No BSL, no "source-available" fine print, no non-compete clauses. A.R.C. is built on a foundation you can fork, modify, and deploy without legal surprises.

### 3. Platform, Not Library

A.R.C. is not another `pip install`. It is a complete ecosystem of pre-wired services: API gateway (Heimdall), secrets vault (Nick Fury), feature flags (Mystique), event streaming (Flash + Dr. Strange), persistent memory (Oracle), reasoning engine (Sherlock), voice pipeline (Scarlett), and full observability (Friday). You pick the profile; we handle the integration.

### 4. Production from Day One

Observability is not an afterthought. Secrets management is not a post-launch scramble. A.R.C. ships with built-in telemetry collection (Friday Collector, OTLP :4317), structured logging, and health checks from the first `arc run`. The `ultra-instinct` profile adds SigNoz (Friday UI, :3301) for full traces + metrics.

### 5. Zero Vendor Lock-In

A.R.C. is built on open standards. Feature flags use Unleash with OpenFeature compatibility — swap providers without rewriting. Observability uses OpenTelemetry — your telemetry pipeline is portable. Every infrastructure service can be replaced without rewriting your agent logic.

### 6. Polyglot Architecture — Two-Brain Separation

Go handles infrastructure: the CLI, bootstrap service (Cortex), and gateway run at compiled speed with no runtime dependencies. Python drives intelligence: Sherlock (LangGraph), Scarlett (Voice Agent), and the SDK use the full Python AI ecosystem. You get the right tool for each layer.

### 7. Capability-Driven Composition

The profile system lets you scale up incrementally:

| Profile | What starts | Use case |
|---------|-------------|----------|
| `think` | Core only (7 services) | Fast iteration, no LLM engine |
| `reason` | Core + Sherlock | Standard AI development |
| `ultra-instinct` | Core + all capabilities | Full platform: voice, observability, security, storage |

### 8. The Codename System

Every A.R.C. service has a memorable codename that reflects its role. Heimdall guards the gate. Sherlock reasons through problems. Flash carries messages at speed. Scarlett handles voice. This makes architecture discussions natural and the system easy to learn. See the full [Service Map](/services/).

## Use Cases

**Voice-First AI Companions** — Scarlett (Voice Agent, port 8803) and Daredevil (LiveKit, port 7880) deliver low-latency, human-grade conversations with full WebRTC support. Enable with the `voice` capability in `ultra-instinct`.

**Stateful Research Agents** — Sherlock (LangGraph, port 8802) and Oracle (PostgreSQL + pgvector, port 5432) keep long-running investigations grounded in persistent, queryable memory. Available in `reason` and `ultra-instinct` profiles.

**Scalable AI Platforms** — Use A.R.C. as the foundation for enterprise AI product suites: event-driven microservices via Flash (NATS) and Dr. Strange (Pulsar), feature flags via Mystique (Unleash), and full observability via Friday — all included.

---

Ready? **[Get Started →](/guide/getting-started)**
