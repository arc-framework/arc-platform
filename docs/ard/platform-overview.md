---
title: Platform Overview
description: End-to-end snapshot of the A.R.C. landing experience in documentation form.
---

# A.R.C. In One Look

**A.R.C. (Agentic Reasoning Core)** is the open-source, distributed intelligence orchestration engine that lets you transform weeks of infrastructure setup into a single command. It is built for teams that want a production-ready "Platform-in-a-Box" without surrendering control of their stack—and who expect every service, codename, and circuit breaker to ship pre-wired.

- **Tagline:** An open-source, modular, Platform-in-a-Box for distributed intelligence.
- **Focus:** Deliver minutes-to-production workflows, full customizability, and an entirely open-source foundation with chaos-tested resilience.
- **Quick Wins:** ⚡ Minutes to deploy · 🔧 Fully customizable · 🌐 Open source · 🛡️ Chaos-ready

---

## 🧠 What is A.R.C.?

A.R.C. is a distributed intelligence orchestration engine designed to remove infrastructure friction so you can focus on what your agents think and do. With a single CLI-driven experience you get a cohesive, battle-tested ecosystem that ships all essential services pre-wired and production-hardened. The platform maps business-critical roles to named services so you always know who is guarding the door, minding the logs, or keeping the neural net honest.

- 🏗️ **Platform, Not Library:** Compose a complete ecosystem with one command—no manual wiring of services.
- ⚡ **Minutes, Not Months:** Go from idea to deployment immediately while A.R.C. handles the plumbing.
- 🔧 **Your Stack, Your Rules:** Everything is standards-based and swappable with zero vendor lock-in.
- 🧭 **Role-Aware Services:** Heimdall (Traefik) gates ingress, Sherlock (LangGraph) reasons, T-800 (Chaos Mesh) pressure-tests the cluster, and Friday (SigNoz) shows the vitals.

---

## ✨ Why Choose A.R.C.?

- **Truly Open-Source:** 100% FOSS (Apache 2.0, MIT, MPL). No BSL, "source-available", or non-compete traps.
- **Platform-in-a-Box:** Heimdall (Traefik), J.A.R.V.I.S. (Kratos), Nick Fury (Infisical), Mystique (Unleash), and more arrive pre-configured.
- **Modular & Pluggable:** Extend and swap components while staying on open standards like OpenFeature and OpenTelemetry.
- **Polyglot Architecture:** High-performance Go gateway and CLI paired with the Python AI ecosystem for agent logic.
- **Cloud-Native:** Containerized, horizontally scalable, and deployable everywhere through a single `arc run`.
- **Event-Driven:** Durable streaming via Dr. Strange (Pulsar) plus real-time messaging with The Flash (NATS).
- **Distributed Intelligence:** Build and orchestrate multi-agent systems with Sherlock, Scarlett, Alfred, and Gordon Ramsay working together.
- **Stateful Agents:** Persist context with Oracle (Postgres + pgvector) and Sonic (Redis) for semantic recall and hot state.
- **Self-Hosted & Resilient:** Own your data, keep everything on-prem if needed, and let the T-800 (Chaos Mesh) validate uptime.

---

## 🛠️ The A.R.C. Journey

1. **Design Your Agent** — Define capabilities, context windows, and reasoning patterns declaratively. _(Focus: capabilities & reasoning)_
2. **Orchestrate Services** — Let A.R.C. auto-compose Heimdall, J.A.R.V.I.S., Mystique, and friends into a cohesive stack. _(Benefit: pre-configured infrastructure)_
3. **Implement Intelligence** — Ship unique agent logic while Sherlock, RoboCop, and Gordon Ramsay handle reasoning, guardrails, and critique. _(Approach: logic over plumbing)_
4. **Deploy & Scale** — Launch with built-in monitoring, tracing, chaos drills, and scaling; no DevOps fire drills. _(Result: production-ready instantly)_

---

## 🔍 Traditional vs. The A.R.C. Way

| Traditional Build                   | The A.R.C. Way                       |
| ----------------------------------- | ------------------------------------ |
| ⏰ Days spent wiring infrastructure | ⚡ Single-command deployment         |
| 🔧 Manual service integration       | 🔗 Heimdall + friends pre-integrated |
| 🔒 Risk of vendor lock-in           | 🆓 Open-source freedom               |
| 🐛 Painful debugging cycles         | 🔍 Sherlock + Friday trace issues    |
| 📈 Scaling bottlenecks              | 🚀 Auto-scaling infrastructure       |
| 👓 Limited observability            | 📊 OTEL + SigNoz built in            |
| 💸 High maintenance costs           | 💰 Cost-effective operations         |
| 📚 Steep learning curves            | 🎯 Production-ready in minutes       |
| 💤 Unknown resilience               | 🛡️ Chaos-tested by the T-800         |

Timeline comparison: **Days of prep** versus **minutes to prod**.

---

## 🚀 Powerful Use Cases

- **Voice-First Companions:** Scarlett (voice agent) plus Daredevil (LiveKit) deliver low-latency, human-grade conversations.
- **Stateful Research Agents:** Sherlock (LangGraph) and Oracle (Postgres) keep long-running investigations grounded in truth.
- **Adversarially Tested Automation:** Ivan Drago (Gym) and the T-800 (Chaos Mesh) stress-test logic and infrastructure before production.
- **Scalable AI Platforms:** Use A.R.C. as the foundation for your own AI product suite across microservices and workers.

---

## 📚 Get Up and Running in Minutes

Dive into the documentation to scaffold your first platform and start composing agents immediately.

- `arc` CLI walkthroughs in [the introduction docs](/guide/getting-started).
- Service-by-service breakdown in [`SERVICE.MD`](https://github.com/arc-framework/arc-platform/blob/main/SERVICE.MD).
- End-to-end platform guides in [`docs/stack`](/services/).
- Source code and community support on [GitHub](https://github.com/arc-framework).

Ready to build? Run `arc new`, follow the prompts, and launch with `arc run`. Your production-ready agent platform is one command away.
