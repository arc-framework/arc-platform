# A.R.C. AI Infrastructure — Design Document

> Status: FIRST DRAFT
> Date: 2026-03-05
> Branch: 014-decouple-service-codenames

## Philosophy

**ARC is not a framework. ARC is AI infrastructure.**

A framework tells you how to build. Infrastructure gives you the primitives and gets out of your way.

ARC bends completely to the user:
- Use one service as a sidecar next to your existing app
- Use the full platform as your AI backbone
- Grow from one to the other without re-architecture

Every ARC service exposes endpoints (REST + async Pulsar topics). Users compose them however they want. ARC has no opinions about how they are wired together — that is the user's domain.

```
ARC provides:  reasoning, memory, retrieval, guardrails, evaluation, training signals
User provides: their data, their models, their business logic, their composition
```

---

## Vision

ARC is AI infrastructure with a **dual deployment spectrum**:

```
← Sidecar ────────────────────────────────────────── Full Platform →
  docker run arc-sherlock               arc run --profile ultra-instinct
  one service, their existing system    entire platform pre-wired, one command
  ARC bends to their stack              their stack grows into ARC
```

Any team (e-commerce, fintech, healthcare, internal tooling) can:

- Drop a single ARC service as a sidecar next to their existing application
- Or adopt ARC fully as a Platform-in-a-Box
- Or grow from sidecar → full platform incrementally, at their own pace

ARC takes enterprise data (static documents + live systems) and exposes intelligent AI primitives as endpoints. What you build with those endpoints is entirely up to you.

---

## How Users Talk to ARC

Every ARC service has exactly two interfaces. No exceptions.

```
REST API       sync    →  immediate response    →  call any service directly, like any HTTP API
Pulsar topic   async   →  event-driven          →  publish work, consume results when ready
```

This applies to ALL services — reasoning, ingestion, search, guardrails, evaluation, everything.

### Access Surface (by priority)

```
1. API   — OpenAI-compatible REST  (Heimdall / arc-gateway → Sherlock / arc-brain)
           drop-in replacement for any existing LLM integration
2. MCP   — Bidirectional MCP hub   (Sherlock as server + client)
           deep enterprise tool integration, AI client connectivity
3. SDK   — Python + Go             (deferred — wraps REST + Pulsar, built after core is stable)
```

Users bring their own LLM API, their own credentials, their own infra. ARC is the AI layer in the middle — it does not own the model, the data, or the business logic.

---

## System 1 — Overall Architecture

```mermaid
graph TB
    subgraph Enterprise["ENTERPRISE BOUNDARY"]
        LLM["Their LLM API\n(OpenAI / Anthropic / Azure / local)"]
        EDB["Their DB / OTEL / Services"]
        ETOOLS["Their Tools\n(CRM, ERP, Order API)"]
    end

    subgraph Access["ACCESS LAYER"]
        A1["1. OpenAI-Compatible API\narc-gateway (Heimdall / Traefik)"]
        A2["2. MCP Hub\narc-brain (Sherlock / LangGraph)"]
        A3["3. Arc SDK\nPython + Go"]
    end

    subgraph Stream["STREAM BACKBONE"]
        NATS["arc-pulse (Flash / NATS)\nspeed path — <200ms TTFT"]
        SH["arc-brain (Sherlock / LangGraph)\nreasoning + orchestration"]
        PULSAR["arc-stream (Dr. Strange / Pulsar)\ndurable fan-out"]
    end

    subgraph Accuracy["ACCURACY LOOP (async, zero latency cost)"]
        RC["arc-guard (RoboCop / Guardrails)\nguardrails + policy"]
        GR["arc-critic (Gordon Ramsay / Critic)\nresponse critique + scoring"]
        ID["arc-gym (Ivan Drago / Trainer)\ntrain + improve"]
    end

    subgraph Data["DATA LAYER"]
        OR["arc-db-sql (Oracle / PostgreSQL + pgvector)\nlong-term memory"]
        SO["arc-db-cache (Sonic / Redis)\nhot state + context cache"]
        CB["arc-db-vector (Cerebro / Qdrant)\nsemantic search"]
        TD["Tardis (MinIO) / arc-storage\nraw file storage"]
    end

    Client["Enterprise App / User"] --> A1
    Client --> A2
    Client --> A3

    A1 --> NATS
    A2 --> NATS
    A3 --> NATS

    NATS --> SH
    SH --> LLM
    SH --> NATS
    SH --> PULSAR

    PULSAR --> RC
    PULSAR --> GR
    PULSAR --> ID

    RC --> GR
    GR --> ID
    ID --> OR

    SH <--> OR
    SH <--> SO
    SH <--> CB
    SH <--> TD

    SH <-->|MCP tool calls| ETOOLS
    SH <-->|model calls| LLM
```

### Two Request Flows

```mermaid
sequenceDiagram
    participant C as Client
    participant H as Heimdall (arc-gateway)
    participant N as Flash (arc-pulse / NATS)
    participant S as arc-brain (Sherlock / LangGraph)
    participant L as LLM API

    rect rgb(20, 60, 20)
        Note over C,L: SYNC FLOW — chat / voice (<200ms TTFT)
        C->>H: POST /v1/chat/completions
        H->>N: publish reasoner.request
        N->>S: deliver
        S->>L: stream tokens
        S-->>N: token chunk 1
        N-->>C: token chunk 1
        S-->>N: token chunk 2
        N-->>C: token chunk 2
        S-->>N: [DONE]
        N-->>C: [DONE]
    end

    rect rgb(20, 20, 60)
        Note over C,L: ASYNC FLOW — background / event-driven
        C->>N: publish to Pulsar topic
        N->>S: Pulsar subscriber triggered
        S->>L: invoke (batch)
        S->>N: publish result to Pulsar out-topic
        N-->>C: consume result when ready
    end
```

---

## System 2 — Data Intelligence Pipeline

How ARC turns enterprise data into smart AI.

> **Core principle:** Static data = context at rest. Live data = context in motion.
> Both are retrieved in parallel at inference time.

```mermaid
graph LR
    subgraph Sources["ENTERPRISE DATA SOURCES"]
        DOC["Documents\nPDF, DOCX, CSV, JSON, TXT"]
        DB["Live Systems\nDB, CRM, ERP, REST APIs"]
        STREAM["Event Streams\norders, transactions, logs"]
    end

    subgraph Ingest["INGESTION PIPELINE (static data)"]
        PARSE["Parse\nreasoner/rag/parsers/"]
        CHUNK["Chunk\nreasoner/rag/chunker.py"]
        EMBED["Embed\nreasoner/rag/adapters/embedder.py"]
        RERANK["Rerank\nreasoner/rag/adapters/reranker.py"]
    end

    subgraph KnowledgeStore["KNOWLEDGE STORE"]
        CB2["arc-db-vector (Cerebro / Qdrant)\nvector search"]
        OR2["arc-db-sql (Oracle / pgvector)\nhybrid search"]
        TD2["Tardis (MinIO) / arc-storage\nraw originals"]
    end

    subgraph Inference["AT INFERENCE TIME (parallel)"]
        Q["Query arrives\narc-pulse (Flash / NATS)"]
        VS["Vector Search\nCerebro + pgvector"]
        MC["MCP Tool Calls\nlive data from enterprise systems"]
        MERGE["Merge context\nstatic + live"]
        LLM2["LLM (their API)\nstream tokens"]
    end

    DOC --> PARSE --> CHUNK --> EMBED --> CB2
    EMBED --> OR2
    DOC --> TD2
    DB --> MC
    STREAM --> PULSAR2["arc-stream (Dr. Strange / Pulsar)"]
    PULSAR2 --> Inference

    Q --> VS
    Q --> MC
    CB2 --> VS
    OR2 --> VS
    VS --> MERGE
    MC --> MERGE
    MERGE --> LLM2
```

### Ingestion Entry Points

```mermaid
graph TD
    E1["File Upload\nREST API multipart"] --> IP["Ingestion Pipeline\nSherlock / arc-brain"]
    E2["S3 / MinIO Sync\nTardis / arc-storage"] --> IP
    E3["URL Crawl\nscheduled or on-demand"] --> IP
    E4["DB Export\nCSV / JSON dump"] --> IP
    E5["MCP Push\nprogrammatic, SDK"] --> IP
    E6["Pulsar Event\nDr. Strange / arc-stream\nreal-time stream ingest"] --> IP

    IP --> CB3["arc-db-vector (Cerebro / Qdrant)"]
    IP --> OR3["arc-db-sql (Oracle / pgvector)"]
    IP --> TD3["Tardis (MinIO) / arc-storage"]
```

---

## System 3 — Accuracy Loop

Runs async on every inference via arc-stream (Dr. Strange / Pulsar) fan-out. Zero latency impact on the speed path.

```mermaid
graph TD
    INF["Every Inference Event\narc-stream (Dr. Strange / Pulsar)"]

    INF --> RC2["arc-guard (RoboCop / Guardrails)\nGuardrails + Safety + Policy"]
    INF --> GR2["arc-critic (Gordon Ramsay / Critic)\nResponse Quality Critique"]
    INF --> ID2["arc-gym (Ivan Drago / Trainer)\nReinforcement + Training Signals"]
    INF --> LOG["arc-friday (Friday / SigNoz)\nObservability + Traces + Metrics"]

    RC2 -->|"violation detected"| BLOCK["Block + Alert\npublish to reasoner.violations\narc-pulse (Flash / NATS)"]
    RC2 -->|"pass"| GR2

    GR2 -->|"scores: relevance\ngroundedness\nhelpfulness"| SCORE["Score Event\npublish to reasoner.scores"]
    SCORE --> ID2

    ID2 -->|"good response"| REINFORCE["Reinforce\nstore as few-shot example\nOracle / arc-db-sql"]
    ID2 -->|"bad response"| RETRAIN["Trigger Re-ingest Signal\nIngestion Pipeline"]
    RETRAIN --> IP2["Ingestion Pipeline\nre-embed corrected data\nSherlock / arc-brain"]
```

### How the System Gets Smarter Over Time

```mermaid
graph LR
    T1["Day 1\nRaw ingestion\nBaseline retrieval"] -->|"RoboCop catches violations"| T2["Week 1\nGuardrails tuned\nPolicy library grows\narc-guard (RoboCop / Guardrails)"]
    T2 -->|"Gordon Ramsay scores responses"| T3["Month 1\nBetter retrieval ranking\nHigh-quality examples stored\narc-critic (Gordon Ramsay / Critic)"]
    T3 -->|"Ivan Drago reinforces patterns"| T4["Month 3\nFine-tuned embeddings\nFew-shot library built\narc-gym (Ivan Drago / Trainer)"]
    T4 -->|"feedback loop continues"| T5["Ongoing\nSelf-improving\nDomain-specific intelligence"]
```

---

## Deployment Spectrum

ARC grows with you. No re-architecture required between stages.

```mermaid
graph TD
    subgraph S1["STAGE 1 — SIDECAR"]
        SA["docker run arc-sherlock (arc-brain)\nOne service alongside existing app\nUser's own DB, auth, OTEL, LLM\nCall POST /v1/chat/completions"]
    end

    subgraph S2["STAGE 2 — CORE AI STACK"]
        SB["arc run --profile think\nHeimdall (arc-gateway)\n+ Flash (arc-pulse / NATS)\n+ arc-brain (Sherlock / LangGraph)\n+ Oracle (arc-db-sql)\n+ Sonic (arc-db-cache)\n+ Cerebro (arc-db-vector)"]
    end

    subgraph S3["STAGE 3 — FULL PLATFORM"]
        SC["arc run --profile ultra-instinct\nAll Stage 2 services\n+ Dr. Strange (arc-stream / Pulsar)\n+ RoboCop (arc-guard)\n+ Gordon Ramsay (arc-critic)\n+ Ivan Drago (arc-gym)\n+ Friday (arc-friday)\n+ T-800 (arc-chaos)"]
    end

    SA -->|"add more services\nno migration"| SB
    SB -->|"add accuracy loop\nno migration"| SC
```

### Sidecar Mode — how it looks in practice

```mermaid
graph LR
    subgraph Existing["EXISTING ENTERPRISE APP"]
        APP["Their application\n(any language, any stack)"]
        EAUTH["Their Auth"]
        EDB2["Their DB"]
        EOTEL["Their OTEL"]
    end

    subgraph ARC["ARC SIDECAR"]
        SH2["arc-brain (Sherlock / LangGraph)\nPOST /v1/chat/completions\nPOST /v1/ingest\nPOST /v1/search"]
    end

    APP -->|"HTTP call"| SH2
    SH2 -->|"model call\n(their LLM API key)"| LLM3["Their LLM API"]
    SH2 -->|"optional: use ARC's DB\nor point at their own"| EDB2
```

---

## Service Reference

| Codename         | Role               | Technology                      | Arc Image            |
| ---------------- | ------------------ | ------------------------------- | -------------------- |
| Heimdall         | Gateway            | Traefik                         | arc-gateway          |
| JARVIS           | Identity           | Kratos                          | arc-identity         |
| Nick Fury        | Secrets            | Infisical                       | arc-vault            |
| Mystique         | Feature Flags      | Unleash                         | arc-flags            |
| Flash            | Messaging          | NATS                            | arc-pulse            |
| Dr. Strange      | Streaming          | Pulsar                          | arc-stream           |
| Oracle           | LT Memory          | PostgreSQL + pgvector           | arc-db-sql           |
| Sonic            | Cache              | Redis                           | arc-db-cache         |
| Cerebro          | Semantic Search    | Qdrant                          | arc-db-vector        |
| Tardis           | Object Storage     | MinIO                           | arc-storage          |
| Sherlock         | Reasoner           | LangGraph                       | arc-brain            |
| Scarlett         | Voice Agent        | LiveKit VAD                     | arc-voice-agent      |
| Daredevil        | Realtime Server    | LiveKit                         | arc-voice-server     |
| RoboCop          | Guardrails         | NeMo Guardrails / Guardrails AI | arc-guard            |
| Gordon Ramsay    | Critic / Evaluator | RAGAs / DeepEval                | arc-critic           |
| Ivan Drago       | Gym / Trainer      | TRL (Hugging Face) + Axolotl    | arc-gym              |
| Friday Collector | OTEL Collector     | SigNoz OTEL                     | arc-friday-collector |
| Friday           | Observability UI   | SigNoz                          | arc-friday           |
| T-800            | Chaos              | Chaos Mesh                      | arc-chaos            |
| Cortex           | Bootstrap          | Go                              | arc-cortex           |

---

## Design Decisions (resolved)

| #   | Question                             | Decision                                                                                              |
| --- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| 1   | MCP direction                        | Bidirectional — Sherlock as MCP server + MCP client hub                                               |
| 2   | SDK                                  | Deferred — build core interfaces + REST API + async topics first. SDK wraps these later.              |
| 3   | RoboCop / Gordon Ramsay / Ivan Drago | Wrap open source: NeMo Guardrails, RAGAs/DeepEval, TRL+Axolotl                                        |
| 4   | Enterprise connectors                | Docker image per connector, enterprise provides connection details (host, creds via Nick Fury)        |
| 5   | Two ways to talk to the system       | REST API (sync) + arc-stream (Dr. Strange / Pulsar) topics (async) — applies to ALL operations, not just ingestion |
| 6   | Profile composition                  | Defer — categorize once services are built                                                            |

---

## System 4 — Resource + Event Pattern (how users extend ARC)

Every ARC resource has two interfaces automatically. This is the **extension model** — enterprises don't need to fork ARC, they subscribe to events.

```mermaid
graph LR
    subgraph Resources["ARC RESOURCES (REST CRUD)"]
        KB["Knowledge Bases\nPOST /v1/knowledge-bases"]
        AG["Agents\nPOST /v1/agents"]
        IG["Ingest\nPOST /v1/ingest"]
        CH["Chat\nPOST /v1/chat/completions"]
        TO["Tools\nPOST /v1/tools"]
    end

    subgraph Events["PULSAR TOPICS (async side-effect of every mutation)"]
        E1["kb.created\nkb.updated\nkb.deleted"]
        E2["agent.created\nagent.updated"]
        E3["ingest.started\ningest.completed\ningest.failed"]
        E4["inference.completed\ninference.failed"]
        E5["tool.registered\ntool.called"]
    end

    subgraph Consumers["ENTERPRISE CONSUMERS (extend without touching ARC)"]
        C1["Compliance Audit\nsubscribe inference.completed"]
        C2["Analytics Pipeline\nsubscribe kb.* + inference.*"]
        C3["Second Model Check\nsubscribe inference.completed"]
        C4["Custom Workflow\nsubscribe any topic"]
    end

    KB -->|"mutation"| E1
    AG -->|"mutation"| E2
    IG -->|"mutation"| E3
    CH -->|"mutation"| E4
    TO -->|"mutation"| E5

    E1 --> Consumers
    E3 --> Consumers
    E4 --> C1
    E4 --> C2
    E4 --> C3
    E4 --> C4
```

> Same pattern as Stripe (REST + webhooks) but Pulsar topics replace webhooks.
> Enterprises subscribe to `Dr. Strange (arc-stream)` topics directly.

---

## System 5 — MCP Hub (bidirectional)

Sherlock sits **in the middle** of the MCP protocol — server to AI clients above, client to enterprise tools below.

```mermaid
graph TB
    subgraph Above["MCP CLIENTS (above ARC)"]
        CL["Claude Desktop / Cursor"]
        GC["GPT / any MCP-compatible AI client"]
        CA["Custom AI Application"]
    end

    subgraph MCPServer["SHERLOCK AS MCP SERVER\narc-brain (Sherlock / LangGraph)"]
        TOOLS["Exposes Tools:\narc_chat, arc_ingest\narc_search, arc_agent_run"]
        PROMPTS["Exposes Prompts:\nagent templates\nRAG prompt patterns"]
        RES["Exposes Resources:\nknowledge bases\nagent configs"]
    end

    subgraph MCPClient["SHERLOCK AS MCP CLIENT\narc-brain (Sherlock / LangGraph)"]
        CONN["Calls Enterprise MCP Servers:\nPostgres connector\nREST API connector\nGraphQL connector\ncustom connectors"]
    end

    subgraph Below["ENTERPRISE MCP SERVERS (below ARC)"]
        DB2["Their Database\narc-mcp-postgres"]
        API["Their REST API\narc-mcp-rest"]
        CRM["Their CRM / ERP\narc-mcp-generic"]
        CUST["Custom connector\narc-mcp-custom"]
    end

    Above -->|"MCP protocol"| MCPServer
    MCPServer --> MCPClient
    MCPClient -->|"MCP protocol"| Below

    DB2 --> Oracle2["arc-db-sql (Oracle / PostgreSQL)\nor their own DB"]
    API --> ETOOLS2["Their live systems"]
```

### MCP Topic Wiring (async path)

```mermaid
sequenceDiagram
    participant AI as Claude Desktop (MCP client)
    participant SH as Sherlock / arc-brain (MCP server)
    participant MC as Enterprise MCP server
    participant P as Dr. Strange (arc-stream / Pulsar)

    AI->>SH: MCP tool call: arc_chat(query)
    SH->>MC: MCP tool call: get_order_status(id)
    MC-->>SH: order data
    SH->>SH: merge context + LLM stream
    SH-->>AI: streaming response (MCP)
    SH->>P: publish inference.completed
    P-->>P: fan-out to accuracy loop
```
