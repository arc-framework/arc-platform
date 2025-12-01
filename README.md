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
| **Resilience** | **T-800** | **Chaos Mesh** | **(NEW)** The Terminator. Randomly kills pods and lags networks to test survival. |

### 🧠 Data & Memory (The Mind)

| Role | Codename | Technology | Description |
| :--- | :--- | :--- | :--- |
| **L.T. Memory** | **Oracle** | **Postgres** | Long-Term Memory. The photographic record of truth. |
| **Working Mem** | **Sonic** | **Redis** | Context Cache. "Gotta go fast." Holds the immediate agent context. |
| **Semantic** | **Cerebro** | **Qdrant** | The Finder. Vector database connecting thoughts via semantic search. |
| **Storage** | **Tardis** | **MinIO** | Infinite Storage. S3-compatible object storage for files/media. |

### 🤖 The AI Workforce (Core & Workers)

Your agents aren't just scripts; they are specialized workers in a distributed system.

* **Sherlock (The Reasoner):** The core **LangGraph** engine. "I cannot make bricks without clay." Handles the complex reasoning loops.
* **Scarlett (The Voice):** The **Voice Agent** core. Turns raw data into human connection (Her).
* **RoboCop (The Guard):** **RuleGo** guardrails. Enforces "Prime Directives" to stop the agent from going rogue.
* **Gordon Ramsay (The Critic):** A specialized worker that yells at your LLM until the output is perfect (QA/Refinement loop).
* **Ivan Drago (The Gym):** An adversarial trainer that attacks your agent's prompts and logic to test for jailbreaks.

### 📊 Observability (The Eyes)

* **Black Widow (OTEL):** Intercepts all signals and traces without being seen.
* **Dr. House (Prometheus):** Diagnostics. Trusts the vitals (metrics), not the patient.
* **Watson (Loki):** The Chronicler. Writes down every log line for later deduction.
* **Columbo (Tempo):** The Detective. Follows the request path (traces) across microservices.

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

We are building A.R.C. in the open. We'd love your help. Please read our **[CONTRIBUTING.md](httpsS://github.com/arc-framework/.github/blob/main/CONTRIBUTING.md)** to get started.

All community interaction is governed by our **[CODE_OF_CONDUCT.md](httpsS://github.com/arc-framework/.github/blob/main/CODE_OF_CONDUCT.md)**.

## 📜 License

A.R.C. is open-source under the **[Apache 2.0 License](httpsS://github.com/arc-framework/arc/blob/main/LICENSE)**.
