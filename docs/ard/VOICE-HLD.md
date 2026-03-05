# Voice Platform — High-Level Design

> **Codename:** Scarlett
> **Status:** Research / Story Grooming
> **Related Spec:** `specs/007-voice-stack/`

---

## Overview

This document covers the high-level design for bringing voice capabilities to the A.R.C. platform. Three modes are in scope:

| Mode | Protocol | Description |
|------|----------|-------------|
| **STT** | REST | Audio file → transcript text |
| **TTS** | REST | Text → audio stream |
| **Audio-to-Audio** | WebSocket (LiveKit room) | Real-time voice conversation via AI agent |

---

## What Already Exists

### Infrastructure (deployed in `services/`)

| Service | Codename | Role | Port(s) |
|---------|----------|------|---------|
| `services/realtime/` | Daredevil | LiveKit WebRTC SFU | 7880 HTTP/WS, 7881 gRPC, 7882 TURN, 50100–50200 UDP |
| `services/realtime/` | Sentry | LiveKit Ingress — RTMP ingest | 1935, 7888 |
| `services/realtime/` | Scribe | LiveKit Egress — recordings → MinIO | 7889 |
| `services/cache/` | Sonic | Redis — LiveKit distributed state | 6379 |
| `services/storage/` | Tardis | MinIO — recording storage (`recordings` bucket) | 9000 |
| `services/messaging/` | Flash | NATS — Scarlett ↔ Sherlock bridge | 4222 |

> Daredevil depends on Sonic. Scribe writes to Tardis. All are in the `reason` profile.

### Voice Agent Proof-of-Concept (`platform-spike`)

A full working pipeline exists at `platform-spike/services/arc-scarlett-voice/`. Not yet migrated to `arc-platform`.

```
User audio
    │
    ▼
Daredevil (WebRTC SFU)
    │
    ▼
Scarlett Agent (livekit-agents SDK)
    ├── Silero VAD         — detects speech end
    ├── Whisper STT        — audio → text  (~200–400ms)
    ├── SherlockLLM plugin — NATS → reasoner.request  (~500–800ms)
    ├── Piper TTS          — text → audio  (~100–300ms)
    └── audio back to room
```

Key spike files to reference during implementation:

| File | Purpose |
|------|---------|
| `platform-spike/services/arc-scarlett-voice/src/agent.py` | VoiceAssistant pipeline |
| `platform-spike/services/arc-scarlett-voice/src/plugins/sherlock_llm.py` | NATS bridge to Sherlock |
| `platform-spike/services/arc-scarlett-voice/src/plugins/piper_tts.py` | Local ONNX TTS plugin |
| `platform-spike/services/arc-scarlett-voice/src/observability.py` | OTEL metrics + traces |
| `platform-spike/services/arc-piper-tts/src/main.py` | Standalone TTS FastAPI service |

---

## Technology Decisions

### LiveKit — No Change

LiveKit handles WebRTC SFU, NAT traversal (STUN/TURN), RTP/RTCP routing, room lifecycle, and provides the Python Agents SDK with pluggable STT/LLM/TTS. No OSS alternative (Janus, mediasoup) provides all of this. Janus/mediasoup require hand-rolling the agent layer. Hosted options (Daily, Agora) are not open-source. **LiveKit stays.**

### No Pipecat

Pipecat introduces its own transport and pipeline abstraction that conflicts with the LiveKit-native approach. The spike already uses `livekit-agents` directly with custom plugins — proven working, simpler dependency tree. Pipecat is excluded.

### Dependency Versions

The spike used old pinned versions. Target latest stable for the migration:

| Package | Spike Version | Target |
|---------|--------------|--------|
| `livekit-agents` | 0.8.0 | latest (~1.x) |
| `livekit` | 0.11.0 | latest |
| `faster-whisper` | 0.10.0 | latest |
| `onnxruntime` | 1.16.3 | latest CPU |
| `nats-py` | 2.6.0 | `>=2.9` (match Sherlock) |

### NATS Subject Alignment

The spike used `brain.request` / `brain.response`. Arc-platform Sherlock uses `reasoner.request`. Scarlett must align to the Reasoner's subjects.

---

## Proposed Service: `services/voice/`

### Identity

```
Codename : Scarlett
Role     : voice
Port     : 8084  (HTTP — health + REST API only, no raw audio)
Image    : ghcr.io/arc-framework/arc-scarlett:latest
Tech     : FastAPI + livekit-agents + faster-whisper + piper-tts
```

### Directory Layout

Follows the same conventions as `services/reasoner/`.

```
services/voice/
├── service.yaml
├── Dockerfile                    # multi-stage, non-root user
├── pyproject.toml                # ruff + mypy + pytest
├── contracts/
│   ├── openapi.yaml              # STT + TTS REST endpoints
│   └── asyncapi.yaml             # NATS session events
└── src/scarlett/
    ├── main.py                   # FastAPI app + lifespan + LiveKit worker start
    ├── config.py                 # Pydantic BaseSettings (SCARLETT_ prefix)
    ├── interfaces.py             # Protocol-based DI (STTPort, TTSPort, LLMPort)
    ├── stt_router.py             # POST /v1/audio/transcriptions
    ├── tts_router.py             # POST /v1/audio/speech
    ├── agent.py                  # LiveKit VoiceAssistant pipeline
    ├── observability.py          # OTEL meter + tracer setup
    └── plugins/
        ├── whisper_stt.py        # faster-whisper STT adapter
        ├── piper_tts.py          # Piper ONNX TTS adapter
        └── sherlock_llm.py       # NATS → reasoner.request LLM adapter
```

---

## HTTP API (OpenAI-Compatible)

Same patterns as Sherlock's routers. Mirrors OpenAI audio API shapes so existing clients work without changes.

### STT — `POST /v1/audio/transcriptions`

```
Content-Type: multipart/form-data

Fields:
  file     — audio file (wav, mp3, m4a, webm, ogg)
  model    — "whisper" (default)
  language — ISO 639-1 code, optional

Response 200:
{
  "text": "Hello, how are you?",
  "language": "en",
  "duration": 3.2
}
```

### TTS — `POST /v1/audio/speech`

```
Content-Type: application/json

{
  "model": "piper",
  "input": "Hello, how can I help you?",
  "voice": "lessac"
}

Response 200: audio/wav stream
Headers: X-Audio-Duration, X-Sample-Rate
```

### Health

```
GET /health       — shallow: process alive + LiveKit reachable
GET /health/deep  — probes LiveKit + NATS connectivity
```

---

## Audio-to-Audio Pipeline (Room-Based)

Not HTTP. The client connects to a Daredevil room via WebSocket. Scarlett's LiveKit worker auto-joins the room and runs the voice loop.

```
Client              Daredevil (7880)        Scarlett Agent
  │── JOIN room ───►│                            │
  │                 │──── worker joins ──────────►│
  │── speak ────────►│                            │
  │                 │──── audio track ───────────►│
  │                 │              │ Silero VAD: speech end
  │                 │              │ Whisper: audio → text
  │                 │              │ NATS publish → reasoner.request
  │                 │              │ Sherlock: text → response
  │                 │              │ Piper: text → audio
  │◄── AI audio ────◄│◄────────────│
```

NATS subject used: `reasoner.request` (Reasoner's queue group: `reasoner_workers`).

---

## STT — Provider Strategy

### Default (local, offline, zero-cost)

- **faster-whisper** — optimized CTranslate2 backend
- Multilingual out of the box
- Model sizes: `tiny` (39 MB, ~150ms) → `base` (74 MB, ~300ms) → `small` (244 MB, ~600ms)
- Configured via `SCARLETT_WHISPER_MODEL=tiny|base|small|medium`

### Cloud-Ready (pluggable, opt-in)

Behind the `STTPort` protocol — drop-in replacements, no pipeline changes:

| Provider | Env Var Value | Notes |
|----------|--------------|-------|
| Deepgram | `deepgram` | Streaming, very low latency |
| Google Speech | `google` | High accuracy, broad language support |
| Azure Cognitive | `azure` | Enterprise SLA |
| OpenAI Whisper API | `openai` | Cloud-hosted Whisper |

Config: `SCARLETT_STT_PROVIDER=whisper` (default)

---

## TTS — Provider Strategy

### Default (local, offline, zero-cost)

- **Piper ONNX** — neural TTS, CPU-only inference
- Default voice: `en_US-lessac-medium` (22050 Hz, WAV 16-bit mono)
- Model baked into Docker image at build time (HuggingFace download)
- Latency: 100–300ms

### Cloud-Ready (pluggable, opt-in)

Behind the `TTSPort` protocol:

| Provider | Env Var Value | Notes |
|----------|--------------|-------|
| ElevenLabs | `elevenlabs` | High quality, streaming |
| Cartesia | `cartesia` | Low latency, streaming |
| OpenAI TTS | `openai` | Multiple voices |
| Azure TTS | `azure` | Enterprise SLA, SSML support |

Config: `SCARLETT_TTS_PROVIDER=piper` (default)

---

## Latency Budget (Audio-to-Audio)

| Stage | Component | Target |
|-------|-----------|--------|
| VAD — speech end detection | Silero | ~20 ms |
| STT — audio to text | Whisper `base` | 200–400 ms |
| NATS round-trip overhead | Flash | 1–5 ms |
| LLM — text to response | Sherlock | 400–800 ms |
| TTS — text to audio | Piper | 100–300 ms |
| WebRTC delivery | Daredevil | ~20 ms |
| **Total** | | **~750–1550 ms** |

Sub-1s is achievable with `tiny` Whisper + a fast/small Sherlock model config.

---

## Infra Dependencies

Scarlett consumes existing infra — **no new services needed**.

| Infra | Codename | Used for |
|-------|----------|---------|
| LiveKit Server | Daredevil | WebRTC room + media routing |
| Redis | Sonic | LiveKit distributed room state |
| NATS | Flash | Scarlett → Sherlock LLM request-reply |
| MinIO | Tardis | Session recordings (via Scribe) |
| OTEL Collector | Friday Collector | Metrics + traces |

`service.yaml` depends_on: `realtime`, `messaging`, `cache`

### Profile Addition

```yaml
# services/profiles.yaml
reason:
  services:
    - ...
    - voice    # Scarlett added here — too heavy for think
```

---

## Observability

OTEL instrumentation following the same patterns as Sherlock and the spike's `observability.py`.

### Metrics

```
scarlett.sessions.total        counter    — LiveKit sessions started
scarlett.utterances.total      counter    — VAD-detected speech turns
scarlett.stt.latency           histogram  — ms, Whisper processing time
scarlett.llm.latency           histogram  — ms, NATS round-trip to Sherlock
scarlett.tts.latency           histogram  — ms, Piper synthesis time
scarlett.pipeline.latency      histogram  — ms, end-to-end per utterance
scarlett.errors.total          counter    — by stage label (stt/llm/tts/room)
```

### Traces

- Span per utterance: `scarlett.utterance` with child spans for STT, LLM, TTS
- NATS context propagation to Sherlock traces

### Structured Logging

- `structlog` JSON, same event pattern as Sherlock: `_log.info("event_name", event_type="...", field=value)`
- Service name: `arc-scarlett`

---

## API Contracts

Two spec files (same convention as `services/reasoner/contracts/`):

**`contracts/openapi.yaml`**
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/speech`
- `GET /health`
- `GET /health/deep`

**`contracts/asyncapi.yaml`**
- NATS publish: `reasoner.request` — utterance forwarded to Sherlock (Reasoner)
- NATS publish: `scarlett.session.started` — room join event
- NATS publish: `scarlett.session.ended` — room leave / timeout event

---

## Stories (SpecKit Backlog)

| # | Story | Notes |
|---|-------|-------|
| S-1 | Scaffold `services/voice/` structure | service.yaml, Dockerfile, pyproject.toml, config.py |
| S-2 | Migrate voice pipeline from spike | Update livekit-agents deps, align NATS subjects |
| S-3 | STT REST endpoint | `POST /v1/audio/transcriptions`, Whisper adapter, OpenAI-compatible |
| S-4 | TTS REST endpoint | `POST /v1/audio/speech`, Piper adapter, OpenAI-compatible |
| S-5 | Voice pipeline wiring | VAD → STT → Sherlock NATS → TTS → room audio |
| S-6 | OTEL instrumentation | Per-stage latency histograms, session counters |
| S-7 | API contracts | `contracts/openapi.yaml` + `contracts/asyncapi.yaml` |
| S-8 | Profile integration | Add `voice` to `reason` profile in `services/profiles.yaml` |
| S-9 | CI/CD | `voice-images.yml` + `voice-release.yml` (follow `realtime-images.yml` pattern) |
| S-10 | Health probes | Shallow + deep health endpoints |

---

## Reference Files

| What | Path |
|------|------|
| Voice agent pipeline (spike) | `platform-spike/services/arc-scarlett-voice/src/agent.py` |
| NATS LLM plugin (spike) | `platform-spike/services/arc-scarlett-voice/src/plugins/sherlock_llm.py` |
| Piper TTS plugin (spike) | `platform-spike/services/arc-scarlett-voice/src/plugins/piper_tts.py` |
| OTEL setup (spike) | `platform-spike/services/arc-scarlett-voice/src/observability.py` |
| Sherlock config pattern | `services/reasoner/src/sherlock/config.py` |
| Sherlock router pattern | `services/reasoner/src/sherlock/files_router.py` |
| Sherlock interfaces | `services/reasoner/src/sherlock/interfaces.py` |
| Sherlock main/lifespan | `services/reasoner/src/sherlock/main.py` |
| Sherlock OpenAPI contract | `services/reasoner/contracts/openapi.yaml` |
| Sherlock AsyncAPI contract | `services/reasoner/contracts/asyncapi.yaml` |
| LiveKit server config | `services/realtime/livekit.yaml` |
| Realtime service definition | `services/realtime/service.yaml` |
| Service profiles | `services/profiles.yaml` |
| Existing voice spec | `specs/007-voice-stack/spec.md` |
