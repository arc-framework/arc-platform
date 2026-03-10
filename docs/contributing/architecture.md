# Architecture

This page explains the three structural concepts that govern how A.R.C. Platform is built and
extended: the Two-Brain separation, the capability system, and service resolution at runtime.

## Two-Brain Separation

The platform separates infrastructure concerns (Go) from intelligence concerns (Python). Go owns
everything that wires the platform together — the CLI, bootstrap, gateway, persistence, messaging,
and cache. Python owns everything that reasons, speaks, and infers — the LLM engine and the voice
agent.

This boundary is a first-class architectural constraint (Constitution §IV). Crossing it (e.g.,
adding Python to a gateway component) requires an ARD.

```mermaid
flowchart TB
    subgraph Go["Go — Infrastructure"]
        CLI["arc CLI\n(cli/)"]
        Cortex["Cortex bootstrap\n(services/cortex/)"]
        Gateway["Heimdall gateway\n(services/gateway/)"]
        Persistence["Oracle DB\n(services/persistence/)"]
        Messaging["Flash NATS\n(services/messaging/)"]
        Cache["Sonic Redis\n(services/cache/)"]
        Streaming["Dr. Strange Pulsar\n(services/streaming/)"]
        Vault["Nick Fury secrets\n(services/secrets/)"]
        Flags["Mystique flags\n(services/flags/)"]
        Storage["Tardis MinIO\n(services/storage/)"]
        Realtime["Daredevil LiveKit\n(services/realtime/)"]
        SDK["Go SDK\n(sdk/go/)"]
    end

    subgraph Python["Python — Intelligence"]
        Reasoner["Sherlock reasoner\n(services/reasoner/)"]
        Voice["Scarlett voice\n(services/voice/)"]
        PySdk["Python SDK\n(sdk/python/)"]
    end

    CLI -->|"orchestrates"| Go
    CLI -->|"orchestrates"| Python
    Reasoner -->|"NATS pub/sub"| Messaging
    Voice -->|"LiveKit rooms"| Realtime
    Reasoner -->|"pgvector queries"| Persistence
```

## Capability System

Services are grouped into capabilities. Capabilities are opt-in — a tier preset selects which
capabilities are active. Core services always run regardless of the selected tier.

The `services/profiles.yaml` file is the single source of truth for capability membership and tier
composition.

```mermaid
flowchart TD
    subgraph Core["Core (always started)"]
        C1[messaging]
        C2[cache]
        C3[streaming]
        C4[cortex]
        C5[persistence]
        C6[gateway]
        C7[friday-collector]
    end

    subgraph Capabilities["Capabilities (opt-in)"]
        CAP_R["reasoner\n→ services/reasoner"]
        CAP_V["voice\n→ services/realtime + voice\n  requires: reasoner"]
        CAP_O["observe\n→ services/otel"]
        CAP_S["security\n→ services/vault + flags"]
        CAP_ST["storage\n→ services/storage"]
    end

    subgraph Tiers["Tier Presets"]
        T1["think\ncapabilities: []"]
        T2["reason\ncapabilities: [reasoner]"]
        T3["ultra-instinct\ncapabilities: '*'"]
    end

    Core --> T1
    Core --> T2
    Core --> T3

    CAP_R --> T2
    CAP_R --> T3
    CAP_V --> T3
    CAP_O --> T3
    CAP_S --> T3
    CAP_ST --> T3
```

## Service Resolution Flow

When `arc run --profile <tier>` (or `make dev PROFILE=<tier>`) is called, the platform resolves the
active service set by combining core services with the services required by each selected
capability.

```mermaid
flowchart LR
    ArcYaml["arc.yaml\ntier: think | reason | ultra-instinct\ncapabilities: [...]"]

    ArcYaml --> Lookup["Look up tier preset\nin profiles.yaml"]
    Lookup --> CapList["Resolved capability list\n(tier preset + explicit overrides)"]
    CapList --> CoreSvcs["Core services\n(always included)"]
    CapList --> CapSvcs["Capability services\n(one set per capability)"]
    CoreSvcs --> ActiveSet["Active service set"]
    CapSvcs --> ActiveSet

    subgraph Examples["Examples"]
        E1["think\n= core only\n(7 services)"]
        E2["reason\n= core + reasoner\n(8 services)"]
        E3["ultra-instinct\n= core + all capabilities\n(14+ services)"]
    end

    ActiveSet --> Examples
```

The CLI passes the resolved set to Docker Compose (or to the container runtime). No service outside
the active set is started, which keeps resource usage proportional to the selected tier.
