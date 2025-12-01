# 📦 A.R.C. Service Registry & Codename Matrix

> **Architect's Note:**
> This isn't just a list of Docker containers; this is the cast of the movie we're building. Every service has a specific job, a personality, and a specific way of ruining your weekend if configured wrong.
>
> We use **codenames** because "Redis" is boring, but "Sonic" tells you _exactly_ what happens if he crashes (you die).

## 🛠️ The Master Service Table

| Service        | A.R.C. Image       | Type    | Upstream Source                | Codename          | Role & "Why Him?"                                                                             |
| :------------- | :----------------- | :------ | :----------------------------- | :---------------- | :-------------------------------------------------------------------------------------------- |
| **Traefik**    | `arc-gateway`      | INFRA   | `traefik:v3.0`                 | **Heimdall**      | **The Gatekeeper.** Opens the Bifrost (ports) only for authorized traffic.                    |
| **Unleash**    | `arc-flags`        | INFRA   | `unleashorg/unleash-server`    | **Mystique**      | **The Shapeshifter.** Changes app behavior flags instantly without redeploying.               |
| **Kratos**     | `arc-identity`     | INFRA   | `oryd/kratos:latest`           | **J.A.R.V.I.S.**  | **The Butler.** "Welcome home, sir." Handles identity and authentication.                     |
| **Infisical**  | `arc-vault`        | INFRA   | `infisical/infisical:latest`   | **Nick Fury**     | **The Spymaster.** Holds the nuclear codes (secrets). Paranoid for a reason.                  |
| **LiveKit**    | `arc-voice-server` | INFRA   | `livekit/livekit-server`       | **Daredevil**     | **The Radar.** Sees the world through sound waves (WebRTC).                                   |
| **NATS**       | `arc-pulse`        | INFRA   | `nats:alpine`                  | **The Flash**     | **The Nervous System.** Information travels so fast it feels like telepathy.                  |
| **Pulsar**     | `arc-stream`       | INFRA   | `apachepulsar/pulsar`          | **Dr. Strange**   | **Time Stone.** Replays history (events) and sees 14 million outcomes.                        |
| **Postgres**   | `arc-db-sql`       | INFRA   | `postgres:16-alpine`           | **Oracle**        | **Long-Term Memory.** The photographic record of truth.                                       |
| **Redis**      | `arc-db-cache`     | INFRA   | `redis:alpine`                 | **Sonic**         | **Working Memory.** "Gotta go fast." Holds context; if he stops, he dies.                     |
| **Qdrant**     | `arc-db-vector`    | INFRA   | `qdrant/qdrant`                | **Cerebro**       | **The Finder.** Connects to every thought to find semantic matches.                           |
| **MinIO**      | `arc-storage`      | INFRA   | `minio/minio`                  | **Tardis**        | **Infinite Storage.** It's bigger on the inside (S3 compatible).                              |
| **OTEL**       | `arc-otel`         | INFRA   | `otel/opentelemetry-collector` | **Black Widow**   | **The Spy.** Intercepts all signals and traces without being seen.                            |
| **Prometheus** | `arc-metrics`      | INFRA   | `prom/prometheus`              | **Dr. House**     | **Diagnostics.** Doesn't trust you; trusts the vitals. "It's never DNS."                      |
| **Loki**       | `arc-logs`         | INFRA   | `grafana/loki`                 | **Watson**        | **The Chronicler.** Writes down every messy detail for later deduction.                       |
| **Tempo**      | `arc-traces`       | INFRA   | `grafana/tempo`                | **Columbo**       | **The Detective.** "Just one more thing." Follows the request path.                           |
| **Grafana**    | `arc-viz`          | INFRA   | `grafana/grafana`              | **Friday**        | **The UI.** The visual interface overlay for the metrics.                                     |
| **Promtail**   | `arc-log-shipper`  | INFRA   | `grafana/promtail`             | **Hermes**        | **The Messenger.** Delivers the logs to Watson.                                               |
| **Chaos**      | `arc-chaos`        | INFRA   | `chaos-mesh/chaos-mesh`        | **T-800**         | **The Terminator.** "It absolutely will not stop until you are dead." Tests infra resilience. |
| **Brain**      | `arc-brain`        | CORE    | `./core/engine`                | **Sherlock**      | **The Reasoner.** "Data! I cannot make bricks without clay." (LangGraph).                     |
| **Voice Agt**  | `arc-voice-agent`  | CORE    | `./core/voice`                 | **Scarlett**      | **The Voice.** Turns raw data into human connection (Her).                                    |
| **Janitor**    | `arc-janitor`      | CORE    | `./core/ops`                   | **The Wolf**      | **The Fixer.** "I solve problems." Cleans up the mess efficiently.                            |
| **Billing**    | `arc-billing`      | CORE    | `./plugins/billing`            | **Alfred**        | **The Manager.** Tracks the budget and manages the estate.                                    |
| **Guard**      | `arc-guard`        | CORE    | `./core/guardrails`            | **RoboCop**       | **Safety.** "Prime Directives." Stops the agent from shooting civilians.                      |
| **Critic**     | `arc-critic`       | WORKER  | `./workers/critic`             | **Gordon Ramsay** | **QA.** "This output is RAW!" Yells until the answer is perfect.                              |
| **Gym**        | `arc-gym`          | WORKER  | `./workers/gym`                | **Ivan Drago**    | **Adversarial Trainer.** "I must break you." Attacks the Agent's logic.                       |
| **Semantic**   | `arc-semantic`     | WORKER  | `./workers/semantic`           | **Uhura**         | **Translator.** Converts human speech to system commands (SQL/API).                           |
| **Mechanic**   | `arc-mechanic`     | WORKER  | `./workers/healer`             | **Statham**       | **Self-Healing.** Slides under the car to fix the leak while running.                         |
| **Migrate**    | `arc-migrate`      | SIDECAR | `script`                       | **Pathfinder**    | **Pioneer.** Maps the database schema before anyone else enters.                              |
| **Ingress**    | `arc-ingress`      | SIDECAR | `livekit/ingress`              | **Sentry**        | **The Watchtower.** Handles incoming RTMP/SIP streams.                                        |
| **Egress**     | `arc-egress`       | SIDECAR | `livekit/egress`               | **Scribe**        | **The Recorder.** Archives the session to tape.                                               |
| **Mailer**     | `arc-mailer`       | SIDECAR | `courier`                      | **Hedwig**        | **Mail Delivery.** Delivers the message no matter what.                                       |

---

## 🤖 The New Recruit: The T-800

We are escalating our testing protocols. We used to just punch the agent (**Ivan Drago**); now we hunt the infrastructure.

- **Service:** `arc-chaos` (Chaos Mesh)
- **Codename:** **T-800** (The Terminator)
- **Mission:** Infrastructure Resilience.
- **Methodology:**
  - **Stress Testing the Mind (Ivan Drago):** Attacks the Prompt/Logic. Tries to jailbreak the LLM or make it hallucinate.
  - **Stress Testing the Body (The Terminator):** Attacks the Server. Kills Redis containers, introduces 500ms network latency, and corrupts disk I/O.

> **Why Him?** > [cite_start]"It can't be bargained with. It can't be reasoned with. It doesn't feel pity, or remorse, or fear. And it absolutely will not stop, ever, until you are dead." [cite: 13]

If your system (A.R.C.) stays online, it is truly resilient. [cite_start]If not... _hasta la vista, baby_[cite: 15].
