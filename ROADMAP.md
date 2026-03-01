# A.R.C. Platform — Roadmap

> **Version**: 1.0.0 | **Date**: 2026-03-01
> **Agentic Reasoning Core** — open-source Platform-in-a-Box for distributed AI agents.

---

## Platform Today

```mermaid
block-beta
  columns 4

  block:infra["Infrastructure (Implemented)"]:4
    otel["001 Friday\nOTEL"]
    cortex["002 Cortex\nBootstrap"]
    nats["003 Flash\nNATS"]
    pulsar["003 Strange\nPulsar"]
  end

  block:data["Data Layer (Implemented)"]:4
    pg["005 Oracle\nPostgreSQL"]
    qd["005 Cerebro\nQdrant"]
    minio["005 Tardis\nMinIO"]
    redis["005 Sonic\nRedis"]
  end

  block:control["Platform Control (Implemented)"]:4
    gw["006 Heimdall\nTraefik"]
    vault["006 Nick Fury\nOpenBao"]
    flags["006 Mystique\nUnleash"]
    dev["004 Dev Setup\nmake dev"]
  end

  block:realtime["Real-Time (Implemented)"]:4
    lk["007 Daredevil\nLiveKit"]
    ingress["007 Sentry\nIngress"]
    egress["007 Scribe\nEgress"]
    specs["008 Specs Site\nVitePress"]
  end

  style infra fill:#1a1a2e,color:#e0e0e0,stroke:#4a9eff
  style data fill:#1a1a2e,color:#e0e0e0,stroke:#4a9eff
  style control fill:#1a1a2e,color:#e0e0e0,stroke:#4a9eff
  style realtime fill:#1a1a2e,color:#e0e0e0,stroke:#4a9eff
```

### What's Missing

```mermaid
mindmap
  root((A.R.C. Gaps))
    Intelligence
      No reasoning engine
      No voice agent
      No agent lifecycle
    Security
      No identity service
      No inter-service auth
      No audit trail
    UX
      CLI directory empty
      SDK directory empty
      No installer
    Ecosystem
      No CI/CD images
      No E2E tests
      No web UI
```

---

## Architecture Target State

```mermaid
graph TB
    subgraph "User Layer"
        WEB[Web UI<br/>React Dashboard]
        CLI_T[A.R.C. CLI<br/>Go Binary]
        SDK_T[Python / Go SDK<br/>pip install arc-sdk]
    end

    subgraph "Gateway Layer"
        GW[Heimdall<br/>Traefik + ForwardAuth]
        RL[Rate Limiter<br/>Redis Quotas]
    end

    subgraph "Identity Layer"
        JARVIS[J.A.R.V.I.S.<br/>Ory Kratos]
        MTLS[Service Auth<br/>OpenBao PKI]
    end

    subgraph "Intelligence Layer"
        SHERLOCK[Sherlock<br/>LangGraph Reasoner]
        SCARLETT[Scarlett<br/>Voice Agent]
        PIPER[Piper<br/>Data Pipeline]
        MULTI[Multi-Agent<br/>Supervisor]
    end

    subgraph "Memory Layer"
        MEM_SDK[arc-memory SDK]
        QD_T[Cerebro — Qdrant]
        PG_T[Oracle — PostgreSQL]
    end

    subgraph "Messaging Layer"
        NATS_T[Flash — NATS]
        PULSAR_T[Strange — Pulsar]
        LK_T[Daredevil — LiveKit]
    end

    subgraph "Observability Layer"
        FRIDAY[Friday — SigNoz]
        AUDIT[Audit Trail<br/>Pulsar → PG]
        T800[T-800<br/>Chaos Mesh]
        DRAGO[Ivan Drago<br/>Adversarial]
    end

    WEB --> GW
    CLI_T --> GW
    SDK_T --> GW

    GW --> JARVIS
    GW --> RL
    JARVIS --> SHERLOCK
    JARVIS --> SCARLETT

    SHERLOCK --> MEM_SDK
    SCARLETT --> SHERLOCK
    MULTI --> SHERLOCK
    PIPER --> MEM_SDK

    MEM_SDK --> QD_T
    MEM_SDK --> PG_T

    SHERLOCK --> NATS_T
    SCARLETT --> LK_T
    SHERLOCK --> PULSAR_T

    SHERLOCK --> FRIDAY
    AUDIT --> PULSAR_T
    AUDIT --> PG_T
    T800 --> NATS_T
    DRAGO --> SHERLOCK

    style SHERLOCK fill:#4a9eff,color:#fff
    style SCARLETT fill:#4a9eff,color:#fff
    style CLI_T fill:#ff6b6b,color:#fff
    style JARVIS fill:#ffd93d,color:#000
    style MULTI fill:#4a9eff,color:#fff
    style PIPER fill:#4a9eff,color:#fff
    style WEB fill:#ff6b6b,color:#fff
```

---

## Phase 1 — Intelligence Layer

> *Build what thinks. You can't demo an AI platform without AI.*

```mermaid
graph LR
    subgraph "009 — Sherlock Reasoning Engine"
        S_API[FastAPI :8083]
        S_GRAPH[LangGraph<br/>StateGraph]
        S_MEM[Memory<br/>Qdrant + PG]
        S_NATS[NATS Handler]
        S_PULSAR[Pulsar Consumer]

        S_API --> S_GRAPH
        S_NATS --> S_GRAPH
        S_PULSAR --> S_GRAPH
        S_GRAPH --> S_MEM
    end

    subgraph "010 — Scarlett Voice Agent"
        SC_LK[LiveKit<br/>Agents SDK]
        SC_STT[STT Pipeline]
        SC_TTS[TTS Pipeline]

        SC_LK --> SC_STT
        SC_STT -->|text| S_NATS
        S_NATS -->|response| SC_TTS
        SC_TTS --> SC_LK
    end

    subgraph "011 — Agent Memory SDK"
        MEM[arc-memory<br/>pip install]
        MEM_Q[Qdrant Adapter]
        MEM_P[Postgres Adapter]
        MEM_E[Embedder]

        MEM --> MEM_Q
        MEM --> MEM_P
        MEM --> MEM_E
    end

    subgraph "012 — Multi-Agent Orchestration"
        SUP[Supervisor<br/>LangGraph]
        AG1[Agent: Research]
        AG2[Agent: Code]
        AG3[Agent: Analysis]

        SUP --> AG1
        SUP --> AG2
        SUP --> AG3
    end

    S_MEM -.->|extracts to| MEM
    SUP -->|delegates to| S_GRAPH

    style S_GRAPH fill:#4a9eff,color:#fff
    style SC_LK fill:#4a9eff,color:#fff
    style MEM fill:#4a9eff,color:#fff
    style SUP fill:#4a9eff,color:#fff
```

| # | Feature | Description | Lang | Deps |
|---|---------|-------------|------|------|
| 009 | **Sherlock Reasoning Engine** | LangGraph v1.0 + Qdrant + NATS — stateful RAG with 3-tier memory | Python | Qdrant, PG, NATS, Pulsar |
| 010 | **Scarlett Voice Agent** | LiveKit Agents SDK — STT → Sherlock → TTS real-time voice loop | Python | LiveKit, Sherlock |
| 011 | **Agent Memory SDK** | `arc-memory` package — Qdrant + Postgres dual-store for any agent | Python | Qdrant, PG |
| 012 | **Multi-Agent Orchestration** | LangGraph supervisor delegating to specialist sub-agents | Python | Sherlock, NATS |

---

## Phase 2 — Platform Hardening

> *Make it safe. No auth = no users.*

```mermaid
graph TB
    subgraph "Identity & Auth"
        KRATOS[013 — J.A.R.V.I.S.<br/>Ory Kratos]
        FWD[014 — ForwardAuth<br/>Traefik Middleware]
        MTLS_S[015 — Service Auth<br/>OpenBao PKI / JWT]
    end

    subgraph "Traffic Control"
        RL_S[016 — Rate Limiting<br/>Traefik + Redis Quotas]
    end

    subgraph "Observability+"
        AUDIT_S[017 — Audit Trail<br/>Pulsar → PG immutable log]
        DASH[018 — SigNoz Dashboards<br/>Pre-configured per service]
        HEALTH[019 — Health Aggregator<br/>Cortex /health/deep]
    end

    subgraph "Request Flow"
        REQ[Incoming Request] --> GW_S[Heimdall<br/>Traefik]
        GW_S --> FWD
        FWD --> KRATOS
        KRATOS -->|session valid| RL_S
        RL_S -->|under quota| SVC[Service]
        SVC --> AUDIT_S
        SVC --> DASH
        HEALTH -.->|probes| SVC
    end

    MTLS_S -.->|cert rotation| SVC

    style KRATOS fill:#ffd93d,color:#000
    style FWD fill:#ffd93d,color:#000
    style MTLS_S fill:#ffd93d,color:#000
    style AUDIT_S fill:#ffd93d,color:#000
```

| # | Feature | Description | Lang | Deps |
|---|---------|-------------|------|------|
| 013 | **J.A.R.V.I.S. Identity** | Ory Kratos — registration, login, sessions, API keys | Config | PG, Redis |
| 014 | **Gateway Auth Middleware** | Traefik ForwardAuth validating Kratos sessions per-request | Config | Traefik, Kratos |
| 015 | **Service-to-Service Auth** | mTLS via OpenBao PKI or JWT validation between services | Config | OpenBao |
| 016 | **Rate Limiting & Quotas** | Per-user token quotas in Redis, enforced at Traefik | Config | Traefik, Redis |
| 017 | **Audit Trail** | Immutable event log — Pulsar topic → Postgres materialized | Python | Pulsar, PG |
| 018 | **SigNoz Dashboards** | Pre-built dashboards for latency, errors, throughput per service | JSON | SigNoz |
| 019 | **Health Aggregator** | Cortex probes all services, returns aggregate deep health | Go | Cortex |

---

## Phase 3 — CLI & Developer Experience

> *Make it usable. The CLI is how developers touch ARC.*

```mermaid
graph TB
    subgraph "arc CLI (Go Binary)"
        ROOT[arc]

        subgraph "020 — Bootstrap"
            VER[arc version]
            HELP[arc help]
            XDG[XDG Paths]
            DB[Embedded State DB]
        end

        subgraph "021 — Run"
            RUN["arc run --profile think"]
            STOP[arc stop]
        end

        subgraph "022 — Status"
            STAT[arc status]
            TUI[BubbleTea TUI<br/>Service Health Grid]
        end

        subgraph "023 — Agent"
            CREATE[arc agent create]
            LIST[arc agent list]
            INSPECT[arc agent inspect]
            DELETE[arc agent delete]
        end

        subgraph "024 — Chat"
            CHAT[arc chat]
            REPL[Interactive REPL<br/>Lipgloss styled]
        end

        subgraph "025 — Config"
            INIT[arc config init]
            SHOW[arc config show]
            EDIT[arc config edit]
        end

        subgraph "026 — Logs"
            LOGS["arc logs [service]"]
            MUX[Multiplexed Tail<br/>Color per service]
        end

        ROOT --> VER
        ROOT --> RUN
        ROOT --> STAT
        ROOT --> CREATE
        ROOT --> CHAT
        ROOT --> INIT
        ROOT --> LOGS

        RUN -->|docker compose| SERVICES[Platform Services]
        STAT -->|HTTP /health| SERVICES
        CREATE -->|NATS publish| SERVICES
        CHAT -->|HTTP POST /chat| SERVICES
        LOGS -->|docker logs| SERVICES
    end

    style ROOT fill:#ff6b6b,color:#fff
    style RUN fill:#ff6b6b,color:#fff
    style CHAT fill:#ff6b6b,color:#fff
    style STAT fill:#ff6b6b,color:#fff
```

| # | Feature | Description | Deps |
|---|---------|-------------|------|
| 020 | **CLI Bootstrap** | `arc` Go binary — Cobra commands, XDG paths, embedded BoltDB state | None |
| 021 | **CLI Run** | `arc run --profile think` — compose orchestration from single binary | Docker |
| 022 | **CLI Status** | `arc status` — BubbleTea TUI grid of service health + resource usage | Services |
| 023 | **CLI Agent** | `arc agent create/list/inspect/delete` — agent CRUD via NATS commands | NATS, Sherlock |
| 024 | **CLI Chat** | `arc chat` — interactive Lipgloss REPL talking to Sherlock | Sherlock |
| 025 | **CLI Config** | `arc config init/show/edit` — manage `arc.yaml` source of truth | None |
| 026 | **CLI Logs** | `arc logs [service]` — multiplexed Docker log tailing with colors | Docker |

---

## Phase 4 — Ecosystem & Release

> *Make it shippable. From repo to community.*

```mermaid
graph LR
    subgraph "SDKs"
        PY_SDK[027 — Python SDK<br/>pip install arc-sdk]
        GO_SDK[028 — Go SDK<br/>go get arc-framework/sdk]
    end

    subgraph "CI/CD"
        IMG[029 — Image Publishing<br/>ghcr.io + semver tags]
        E2E[030 — E2E Tests<br/>Profile → Agent → Trace]
    end

    subgraph "Resilience"
        T800_S[031 — T-800 Chaos<br/>Chaos Mesh]
        DRAGO_S[037 — Ivan Drago<br/>Adversarial Testing]
    end

    subgraph "Content"
        DOCS[032 — Docs Site<br/>Docusaurus]
        INSTALL[033 — CLI Installer<br/>curl + Homebrew]
    end

    subgraph "Advanced"
        MARKET[034 — Agent Marketplace<br/>Template Registry]
        PLUGIN[035 — Plugin System<br/>Custom Tools + LLMs]
        DEPLOY[036 — Cloud Deploy<br/>K8s / Fly.io]
        PIPER_S[038 — Piper Pipeline<br/>Doc Ingestion ETL]
        WEBUI[039 — Web UI<br/>React Dashboard]
    end

    PY_SDK --> E2E
    GO_SDK --> E2E
    IMG --> INSTALL
    E2E --> T800_S
    DOCS --> INSTALL
    MARKET --> PLUGIN
    PIPER_S --> WEBUI
    DEPLOY --> IMG

    style PY_SDK fill:#6bcb77,color:#000
    style GO_SDK fill:#6bcb77,color:#000
    style WEBUI fill:#6bcb77,color:#000
    style DEPLOY fill:#6bcb77,color:#000
```

| # | Feature | Description |
|---|---------|-------------|
| 027 | **Python SDK** | `pip install arc-sdk` — typed async client for chat, memory, agents, real-time |
| 028 | **Go SDK** | `go get arc-framework/sdk` — Go client for CLI and infrastructure integrations |
| 029 | **Docker Image Publishing** | GitHub Actions pipeline — build, test, publish all images to ghcr.io with semver |
| 030 | **E2E Test Suite** | Spin up `think` profile → run agent conversation → verify traces in SigNoz |
| 031 | **T-800 Chaos Testing** | Chaos Mesh — kill services, partition networks, verify auto-recovery |
| 032 | **Documentation Site** | Docusaurus — quickstart, architecture guide, API reference, tutorials |
| 033 | **CLI Installer** | `curl -fsSL install.sh` + Homebrew tap + apt/dnf repos |
| 034 | **Agent Marketplace** | Template registry — `arc agent create --template customer-support` |
| 035 | **Plugin System** | Python hooks for custom tools, memory providers, LLM backends |
| 036 | **Cloud Deploy** | `arc deploy` — generate K8s manifests or push to Fly.io |
| 037 | **Ivan Drago Adversarial** | Prompt injection, hallucination, and safety testing for agents |
| 038 | **Piper Data Pipeline** | ETL for document ingestion — PDF, markdown, web → Qdrant vectors |
| 039 | **Web UI** | React dashboard — chat, agent management, memory explorer, trace viewer |

---

## Dependency Graph

```mermaid
graph TD
    %% Phase 1
    009[009 Sherlock] --> 010[010 Scarlett]
    009 --> 011[011 Memory SDK]
    009 --> 012[012 Multi-Agent]
    011 --> 012

    %% Phase 2
    013[013 J.A.R.V.I.S.] --> 014[014 Gateway Auth]
    013 --> 015[015 Service Auth]
    013 --> 016[016 Rate Limiting]
    013 --> 017[017 Audit Trail]
    009 --> 018[018 Dashboards]
    009 --> 019[019 Health Aggregator]

    %% Phase 3
    020[020 CLI Bootstrap] --> 021[021 CLI Run]
    020 --> 025[025 CLI Config]
    021 --> 022[022 CLI Status]
    021 --> 026[026 CLI Logs]
    009 --> 023[023 CLI Agent]
    020 --> 023
    009 --> 024[024 CLI Chat]
    020 --> 024

    %% Phase 4
    009 --> 027[027 Python SDK]
    020 --> 028[028 Go SDK]
    027 --> 030[030 E2E Tests]
    028 --> 030
    021 --> 029[029 Image Publish]
    029 --> 033[033 Installer]
    030 --> 031[031 T-800 Chaos]
    009 --> 037[037 Ivan Drago]
    027 --> 032[032 Docs Site]
    027 --> 034[034 Marketplace]
    027 --> 035[035 Plugins]
    029 --> 036[036 Cloud Deploy]
    011 --> 038[038 Piper ETL]
    027 --> 039[039 Web UI]

    %% Styling
    classDef phase1 fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef phase2 fill:#ffd93d,color:#000,stroke:#c9a800
    classDef phase3 fill:#ff6b6b,color:#fff,stroke:#c93c3c
    classDef phase4 fill:#6bcb77,color:#000,stroke:#3d9944

    class 009,010,011,012 phase1
    class 013,014,015,016,017,018,019 phase2
    class 020,021,022,023,024,025,026 phase3
    class 027,028,029,030,031,032,033,034,035,036,037,038,039 phase4
```

---

## Timeline & Milestones

```mermaid
gantt
    title A.R.C. Platform Roadmap
    dateFormat YYYY-MM-DD
    axisFormat %b %Y

    section Phase 1 — Intelligence
    009 Sherlock Reasoning     :active, p009, 2026-03-01, 21d
    010 Scarlett Voice         :p010, after p009, 14d
    011 Agent Memory SDK       :p011, after p009, 10d
    012 Multi-Agent            :p012, after p011, 14d

    section Phase 2 — Hardening
    013 J.A.R.V.I.S. Identity :p013, after p009, 14d
    014 Gateway Auth           :p014, after p013, 7d
    015 Service Auth           :p015, after p013, 10d
    016 Rate Limiting          :p016, after p014, 7d
    017 Audit Trail            :p017, after p013, 10d
    018 SigNoz Dashboards      :p018, after p009, 7d
    019 Health Aggregator      :p019, after p009, 7d

    section Phase 3 — CLI
    020 CLI Bootstrap          :p020, after p012, 14d
    021 CLI Run                :p021, after p020, 10d
    022 CLI Status             :p022, after p021, 7d
    023 CLI Agent              :p023, after p020, 10d
    024 CLI Chat               :p024, after p020, 7d
    025 CLI Config             :p025, after p020, 7d
    026 CLI Logs               :p026, after p021, 5d

    section Phase 4 — Ecosystem
    027 Python SDK             :p027, after p016, 14d
    028 Go SDK                 :p028, after p020, 14d
    029 Image Publishing       :p029, after p021, 7d
    030 E2E Tests              :p030, after p027, 10d
    031 T-800 Chaos            :p031, after p030, 10d
    032 Docs Site              :p032, after p027, 14d
    033 CLI Installer          :p033, after p029, 5d
    038 Piper Pipeline         :p038, after p011, 14d
    039 Web UI                 :p039, after p027, 21d
```

---

## Service Matrix — Full Roster

```mermaid
graph TB
    subgraph "Infrastructure Brain (Go)"
        direction TB
        CORTEX[Cortex<br/>Bootstrap]
        GW_M[Heimdall<br/>Gateway]
        JARVIS_M[J.A.R.V.I.S.<br/>Identity]
        FURY[Nick Fury<br/>Secrets]
        MYSTIQUE[Mystique<br/>Flags]
        CLI_M[A.R.C. CLI<br/>Go Binary]
    end

    subgraph "Intelligence Brain (Python)"
        direction TB
        SHERLOCK_M[Sherlock<br/>Reasoning]
        SCARLETT_M[Scarlett<br/>Voice]
        PIPER_M[Piper<br/>Data Pipeline]
        DRAGO_M[Ivan Drago<br/>Adversarial]
        MEM_M[arc-memory<br/>SDK]
    end

    subgraph "Data Stores"
        direction TB
        ORACLE[Oracle<br/>PostgreSQL]
        CEREBRO[Cerebro<br/>Qdrant]
        TARDIS[Tardis<br/>MinIO]
        SONIC[Sonic<br/>Redis]
    end

    subgraph "Messaging"
        direction TB
        FLASH[Flash<br/>NATS]
        STRANGE[Dr. Strange<br/>Pulsar]
        DAREDEVIL[Daredevil<br/>LiveKit]
    end

    subgraph "Observability"
        direction TB
        FRIDAY_M[Friday<br/>SigNoz + OTEL]
        T800_M[T-800<br/>Chaos Mesh]
    end

    CLI_M --> GW_M
    GW_M --> JARVIS_M
    GW_M --> SHERLOCK_M
    SHERLOCK_M --> CEREBRO
    SHERLOCK_M --> ORACLE
    SHERLOCK_M --> FLASH
    SCARLETT_M --> DAREDEVIL
    SCARLETT_M --> SHERLOCK_M
    PIPER_M --> CEREBRO
    CORTEX --> ORACLE
    CORTEX --> FLASH
    CORTEX --> STRANGE

    classDef go fill:#00ADD8,color:#fff,stroke:#007d9c
    classDef python fill:#3776AB,color:#fff,stroke:#1e4f72
    classDef data fill:#336791,color:#fff,stroke:#1d3d56
    classDef msg fill:#8B5CF6,color:#fff,stroke:#6d3fc4
    classDef obs fill:#F97316,color:#fff,stroke:#c35d12

    class CORTEX,GW_M,JARVIS_M,FURY,MYSTIQUE,CLI_M go
    class SHERLOCK_M,SCARLETT_M,PIPER_M,DRAGO_M,MEM_M python
    class ORACLE,CEREBRO,TARDIS,SONIC data
    class FLASH,STRANGE,DAREDEVIL msg
    class FRIDAY_M,T800_M obs
```

---

## Profile Evolution

```mermaid
graph LR
    subgraph "think (Minimal — just enough to think)"
        T_MSG[Flash]
        T_CACHE[Sonic]
        T_STREAM[Strange]
        T_OTEL[Friday Collector]
        T_CORTEX[Cortex]
        T_PG[Oracle]
        T_QD[Cerebro]
        T_GW[Heimdall]
        T_LK[Daredevil]
    end

    subgraph "reason (Dev — think + intelligence + observability)"
        R_ALL["Everything in think"]
        R_SHERLOCK[Sherlock ★]
        R_JARVIS[J.A.R.V.I.S. ★]
        R_SIGVIZ[Friday UI ★]
        R_VAULT[Nick Fury]
        R_FLAGS[Mystique]
        R_STORE[Tardis]
    end

    subgraph "ultra-instinct (Full — every service)"
        U_ALL["Everything in reason"]
        U_SCARLETT[Scarlett ★]
        U_PIPER[Piper ★]
        U_MULTI[Multi-Agent ★]
        U_DRAGO[Ivan Drago ★]
        U_T800[T-800 ★]
        U_INGRESS[Sentry]
        U_EGRESS[Scribe]
    end

    T_MSG --> R_ALL
    R_ALL --> U_ALL

    style R_SHERLOCK fill:#4a9eff,color:#fff
    style R_JARVIS fill:#ffd93d,color:#000
    style U_SCARLETT fill:#4a9eff,color:#fff
    style U_PIPER fill:#4a9eff,color:#fff
```

> **★** = new services added by this roadmap

---

## Build Order — Critical Path

```mermaid
graph LR
    A["009 Sherlock<br/>(in progress)"] -->|unlocks| B["010 Scarlett<br/>011 Memory SDK"]
    B -->|unlocks| C["012 Multi-Agent<br/>013 J.A.R.V.I.S."]
    C -->|unlocks| D["020 CLI Bootstrap"]
    D -->|unlocks| E["021-026<br/>CLI Commands"]
    E -->|unlocks| F["027-028<br/>SDKs"]
    F -->|unlocks| G["029-039<br/>Ship It"]

    style A fill:#4a9eff,color:#fff
    style B fill:#4a9eff,color:#fff
    style C fill:#ffd93d,color:#000
    style D fill:#ff6b6b,color:#fff
    style E fill:#ff6b6b,color:#fff
    style F fill:#6bcb77,color:#000
    style G fill:#6bcb77,color:#000
```

### Why This Order

1. **Intelligence first** — Sherlock + Scarlett give you the demo: *"talk to an AI agent that remembers."* Everything else is plumbing until reasoning works.
2. **Hardening before CLI** — the CLI calls services. If auth doesn't exist, the CLI ships insecure. J.A.R.V.I.S. must exist before `arc chat` sends tokens.
3. **CLI before SDK** — the CLI *is* the first user. Building it defines the UX: what does `arc run` do? What does `arc agent create` need? The SDK wraps what the CLI already validated.
4. **SDK before ecosystem** — E2E tests, docs, and the web UI all consume the SDK. Ship the SDK, then build everything on top of it.
