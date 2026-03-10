---
layout: home

hero:
  name: "A.R.C."
  text: "Agentic Reasoning Core"
  tagline: The open-source Platform-in-a-Box for building, deploying, and orchestrating production-ready AI agents. One command. Zero weeks of infrastructure work.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: Why A.R.C.?
      link: /guide/why-arc
    - theme: alt
      text: GitHub
      link: https://github.com/arc-framework/arc-platform

features:
  - icon: 🚀
    title: Platform-in-a-Box
    details: One command — `arc run --profile think` — bootstraps a full AI agent platform. Gateway, messaging, persistence, cache, and reasoning engine. All pre-wired.
  - icon: 🔓
    title: Truly Open-Source
    details: 100% of the core stack is FOSS — Apache 2.0, MIT, or MPL. No BSL, no source-available fine print, no non-compete clauses. Fork it, ship it, own it.
  - icon: 🔌
    title: Modular & Composable
    details: Flat service layout composed by capability profiles. Start with `think` (core only), scale to `ultra-instinct` (all capabilities). Swap any service without rewriting agent logic.
  - icon: 🧠
    title: Two-Brain Architecture
    details: Go handles infrastructure at compiled speed. Python drives intelligence with LangGraph, Whisper, and Piper. The right tool for each layer.
  - icon: 📡
    title: Event-Driven by Default
    details: Durable streaming with Apache Pulsar (Dr. Strange) and ephemeral messaging with NATS (Flash) for real-time, distributed intelligence that scales.
  - icon: 🗄️
    title: Stateful Agents
    details: Long-term memory and semantic search with PostgreSQL + pgvector (Oracle). Agents that remember, reason over history, and learn over time.
  - icon: ☁️
    title: Cloud-Native
    details: Fully containerized, horizontally scalable, and deployable anywhere Docker runs. Local-first development, production-ready from day one.
  - icon: 📊
    title: Observability by Default
    details: OTEL traces, metrics, and structured logs built into every service. Friday Collector (OTEL) runs in every profile. SigNoz UI in `ultra-instinct`.
  - icon: 🏠
    title: Self-Hosted
    details: Your data never leaves your infrastructure. No external API dependencies for core agent logic. Air-gapped deployments supported.
---

## The A.R.C. Way

| Without A.R.C. | With A.R.C. |
|----------------|-------------|
| Days wiring infrastructure | Single-command deployment with `arc run` |
| Manual service integration | Pre-integrated: Heimdall, Flash, Sherlock, and more |
| Painful observability setup | OTEL + SigNoz built in from day one |
| Vendor lock-in | 100% open-source, open standards (OpenTelemetry, OpenFeature) |
| Unknown resilience | Chaos-tested infrastructure before production |
| Steep learning curve | Production-ready in minutes |

## What You Can Build

**Voice-First AI Companions** — Scarlett (Voice Agent) and Daredevil (LiveKit) deliver low-latency, human-grade conversations with full WebRTC support over port 8803.

**Stateful Research Agents** — Sherlock (LangGraph, port 8802) and Oracle (PostgreSQL + pgvector) keep long-running investigations grounded in persistent, queryable memory.

**Scalable AI Platforms** — Use A.R.C. as the foundation for enterprise AI product suites — event-driven microservices, feature flags, full observability, all included.

## Quick Start

```bash
# Install the CLI
brew install arc-framework/tap/arc   # macOS
# or download from github.com/arc-framework/arc-platform/releases

# Initialize a workspace
arc workspace init ./my-project
cd my-project

# Launch the platform (core + reasoning engine)
arc run --profile reason

# Check everything is healthy
make dev-health
```

→ [Full getting started guide](/guide/getting-started)
