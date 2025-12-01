<p align="center">
  <img src="https://raw.githubusercontent.com/arc-framework/.github/main/assets/arc-icon.png" alt="A.R.C. Agentic Reasoning Core Banner" width="800" />
</p>

<p align="center">
  <strong>A.R.C. (Agentic Reasoning Core)</strong>
  <br />
  An open-source, "Platform-in-a-Box" for building, deploying, and orchestrating production-ready AI agents.
</p>

---

## 🧠 What is A.R.C.?

**A.R.C. (Agentic Reasoning Core)** is an open-source, modular, and cloud-native AI system designed to be a distributed intelligence orchestration engine.

But A.R.C. isn't just another Python library—it's a **"Platform-in-a-Box."**

It's a production-ready ecosystem of pre-built, "black-box" services that you compose and control. We provide the "batteries-included" infrastructure (like IAM, streaming, and API gateways) so you can stop worrying about plumbing and focus on what matters: **building the "thinking engine" for your agents.**

Use A.R.C. to build, deploy, and scale:
* Voice-first AI companions (powered by **Scarlett**)
* Stateful, long-running research agents (powered by **Sherlock**)
* Adversarially tested logic flows (trained by **Ivan Drago**)
* Modular, event-driven AI microservices

---

## ✨ Why A.R.C.?

* **Truly Open-Source:** 100% of our core stack is **FOSS**. No BSL, source-available, or proprietary-core-with-non-compete-clauses. We're built on Apache 2.0, MIT, and MPL.
* **Platform-in-a-Box:** We provide the "batteries-included" foundation. You get auth, secrets, messaging, and observability out of the box, not as an afterthought.
* **Modular & Pluggable:** We're built on standards. We use **OpenFeature** for feature flags and **OpenTelemetry** for observability, so you're never locked into a single vendor (not even us).
* **Built for Resilience:** Our stack isn't a toy. It includes **Chaos Engineering** by default to ensure your agents survive the real world.

---

## 🧩 The A.R.C. Stack (The Service Matrix)

A.R.C. is a polyglot platform managed by a single powerful CLI. We map industry-standard open-source technology to specific "Roles" within the cluster.

### 🛡️ Infrastructure (The Body)

| Role | Codename | Technology | Description |
| :--- | :--- | :--- | :--- |
| **Gateway** | **Heimdall** | **Traefik** | The Gatekeeper. Opens the Bifrost (ports) only for authorized traffic. |
| **Identity** | **J.A.R.V.I.S.** | **Kratos** | The Butler. Handles identity, authentication, and user sessions. |
| **Secrets** | **Nick Fury** | **Infisical** | The Spymaster. Securely holds the nuclear codes (API keys & secrets). |
| **Flags** | **Mystique** | **Unleash** | The Shapeshifter. Changes app behavior flags instantly without redeploying. |
| **Events** | **Dr. Strange** | **Pulsar** | Time Stone. Replays event history and manages the durable stream. |
| **Messaging** | **The Flash** | **NATS** | The Nervous System. High-speed, ephemeral messaging for the cluster. |
| **Real-Time** | **Daredevil** | **LiveKit** | The Radar. Sees the world through sound waves (WebRTC). |
| **Delivery** | **Hedwig** | **Mailer** | Mail Delivery. Delivers the message (emails) no matter what. |
| **Resilience** | **T-800** | **Chaos Mesh** | **(NEW)** The Terminator. Randomly kills pods to test survival. |

### 🧠 Data & Memory (The Mind)

| Role | Codename | Technology | Description |
| :--- | :--- | :--- | :--- |
| **L.T. Memory** | **Oracle** | **Postgres** | Long-Term Memory. The photographic record of truth. |
| **Working Mem** | **Sonic** | **Redis** | Context Cache. "Gotta go fast." Holds the immediate agent context. |
| **Semantic** | **Cerebro** | **Qdrant** | The Finder. Vector database connecting thoughts via semantic search. |
| **Storage** | **Tardis** | **MinIO** | Infinite Storage. S3-compatible object storage for files/media. |
| **Pioneer** | **Pathfinder** | **Migrate** | Maps the database schema before anyone else enters. |

### 🤖 The AI Workforce (Core & Workers)

Your agents aren't just scripts; they are specialized workers in a distributed system.

| Role | Codename | Technology | Description |
| :--- | :--- | :--- | :--- |
| **Reasoner** | **Sherlock** | **LangGraph** | The Core Engine. "Data! I cannot make bricks without clay." |
| **Voice** | **Scarlett** | **Voice Agent** | The Voice. Turns raw data into human connection (Her). |
| **Guard** | **RoboCop** | **RuleGo** | Safety. Enforces "Prime Directives" to stop the agent from shooting civilians. |
| **Critic** | **Gordon Ramsay**| **QA Worker** | "This output is RAW!" Yells until the LLM's answer is perfect. |
| **Gym** | **Ivan Drago** | **Adv. Trainer**| "I must break you." Attacks the Agent's logic to find weaknesses. |
| **Translator**| **Uhura** | **Semantic** | Converts human speech/intent to system commands (SQL/API). |
| **Mechanic** | **Statham** | **Healer** | Self-Healing. Slides under the car to fix leaks while running. |
| **Janitor** | **The Wolf** | **Ops** | "I solve problems." Cleans up the mess efficiently. |
| **Manager** | **Alfred** | **Billing** | Tracks the budget and manages the estate. |
| **Sentry** | **Sentry** | **Ingress** | The Watchtower. Handles incoming RTMP/SIP streams for LiveKit. |
| **Scribe** | **Scribe** | **Egress** | The Recorder. Archives LiveKit sessions to tape. |

### 📊 Observability (The Eyes)

| Role | Codename | Technology | Description |
| :--- | :--- | :--- | :--- |
| **Collector** | **Black Widow** | **OTEL** | The Spy. Intercepts all signals and traces without being seen. |
| **Metrics** | **Dr. House** | **Prometheus** | Diagnostics. Trusts the vitals, not the patient. |
| **Logs** | **Watson** | **Loki** | The Chronicler. Writes down every messy detail for later deduction. |
| **Traces** | **Columbo** | **Tempo** | The Detective. "Just one more thing." Follows the request path. |
| **UI** | **Friday** | **Grafana** | The visual interface overlay for all metrics and logs. |
| **Shipper** | **Hermes** | **Promtail** | The Messenger. Delivers the logs to Watson. |

---

## 💡 How It Works (The "A.R.C. Way")

We've designed A.R.C. to have the power of a microservice architecture, with the simple developer experience of a monolith.

1.  **Interactive Scaffolding**
    It all starts with the `arc` CLI wizard. This tool guides you through a series of questions to understand what your platform needs.

2.  **Smart Composition**
    Based on your answers, the A.R.C. framework acts as a "smart scaffolder." It dynamically generates a new, fully-configured project, composing our pre-built services (Heimdall, J.A.R.V.I.S., Sherlock) into a single, cohesive `docker-compose.yml`.

3.  **One-Command Launch**
    The entire, complex, multi-service platform—which would normally take weeks to configure—launches locally with a single `arc run` command.

4.  **Focus on the "Thinking Engine"**
    Your job is not to build infrastructure. The plumbing is done. Your only task is to open the **Sherlock** (`arc-brain`) service and start writing your unique agent logic using LangGraph.

---

## 🤝 Contributing

We are building A.R.C. in the open. We'd love your help. Please read our **[CONTRIBUTING.md](https://github.com/arc-framework/.github/blob/main/CONTRIBUTING.md)** to get started.

All community interaction is governed by our **[CODE_OF_CONDUCT.md](https://github.com/arc-framework/.github/blob/main/CODE_OF_CONDUCT.md)**.

## 📜 License

A.R.C. is open-source under the **[Apache 2.0 License](https://github.com/arc-framework/arc/blob/main/LICENSE)**.
