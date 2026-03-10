---
url: /arc-platform/docs/services/voice.md
---
# Voice — Scarlett

Voice agent service providing STT (Whisper) and TTS (Piper) over an OpenAI-compatible HTTP API.

> **Status: In development.** Makefile registration is pending. The container and CI workflow exist on branch `016-voice-system`; make targets listed below are planned for the `ultra-instinct` profile.

| Field | Value |
|-------|-------|
| Codename | Scarlett |
| Container | `arc-voice-agent` |
| Port | 8803 |
| Health URL | `http://localhost:8803/health` |
| Profiles | ultra-instinct (voice capability) |
| Source | `services/voice/` |

## Make Targets

```bash
make voice-up       # start arc-voice-agent container
make voice-down     # stop arc-voice-agent container
make voice-health   # curl /health
make voice-logs     # follow container logs
make voice-test     # run pytest suite
make voice-lint     # ruff + mypy
```

## HTTP API

### POST /v1/audio/transcriptions

Transcribe an audio file using Whisper. Accepts any `audio/*` MIME type via multipart form upload.

**Request** (multipart/form-data):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | yes | Audio file — any `audio/*` MIME type |
| `model` | string | no | Whisper model name (default: configured at startup) |
| `language` | string | no | BCP-47 language code, e.g. `en` |
| `response_format` | string | no | Response format — `json` (default) |

```bash
curl -s -X POST http://localhost:8803/v1/audio/transcriptions \
  -F "file=@recording.wav;type=audio/wav" \
  -F "model=whisper-1" \
  -F "language=en"
```

**Response (200):**

```json
{
  "text": "Hello, how can I help you today?",
  "language": "en",
  "duration": 2.45
}
```

**Error response (400)** — unsupported content type:

```json
{
  "error_type": "invalid_input",
  "message": "Unsupported content type: 'image/png'. Expected audio/*.",
  "correlation_id": "a1b2c3d4-..."
}
```

**Error response (502)** — Whisper provider unavailable:

```json
{
  "error_type": "provider_unavailable",
  "message": "Whisper model failed to load: ...",
  "correlation_id": "a1b2c3d4-..."
}
```

***

### POST /v1/audio/speech

Synthesize speech from text using Piper TTS. Returns a WAV audio stream.

**Request** (application/json):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | yes | — | Model identifier (passed through; Piper uses a single configured model) |
| `input` | string | yes | — | Text to synthesize — must not be empty |
| `voice` | string | no | `"default"` | Voice name |
| `response_format` | string | no | `"wav"` | Output format — `wav` |

```bash
curl -s -X POST http://localhost:8803/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "piper-1",
    "input": "Hello, welcome to the ARC platform.",
    "voice": "default",
    "response_format": "wav"
  }' \
  --output speech.wav
```

**Response headers:**

| Header | Description |
|--------|-------------|
| `Content-Type` | `audio/wav` |
| `X-Duration-Seconds` | Duration of synthesized audio in seconds |
| `X-Sample-Rate` | Sample rate of the output WAV |

The response body is a raw WAV byte stream.

**Error response (400)** — empty input:

```json
{
  "error_type": "invalid_input",
  "message": "'input' must not be empty.",
  "correlation_id": "a1b2c3d4-..."
}
```

**Error response (502)** — Piper provider unavailable:

```json
{
  "error_type": "provider_unavailable",
  "message": "Piper binary not found at /usr/local/bin/piper",
  "correlation_id": "a1b2c3d4-..."
}
```

***

### GET /health

Shallow liveness probe. Returns immediately without calling dependencies.

```bash
curl -s http://localhost:8803/health
```

```json
{"status": "ok"}
```

***

### GET /health/deep

Readiness probe. Checks connectivity to `arc-realtime` (LiveKit) and `arc-messaging` (NATS) in parallel. Always returns HTTP 200; the `status` field indicates overall health.

```bash
curl -s http://localhost:8803/health/deep
```

**Healthy response:**

```json
{
  "status": "ok",
  "checks": {
    "arc-realtime": {"status": "ok", "latency_ms": 3.2},
    "arc-messaging": {"status": "ok", "latency_ms": 1.8}
  }
}
```

**Degraded response:**

```json
{
  "status": "degraded",
  "checks": {
    "arc-realtime": {"status": "degraded", "reason": "Connection refused", "latency_ms": 0.4},
    "arc-messaging": {"status": "ok", "latency_ms": 2.1}
  }
}
```

***

## NATS Event Topics

The voice agent publishes lifecycle events to NATS for observability and downstream consumers. These are fire-and-forget — no subscription is expected.

| Topic | Event | Description |
|-------|-------|-------------|
| `arc.voice.session.started` | `VoiceSessionStartedEvent` | Participant joined a LiveKit room |
| `arc.voice.session.ended` | `VoiceSessionEndedEvent` | Session concluded; includes duration |
| `arc.voice.turn.completed` | `VoiceTurnCompletedEvent` | Full STT → bridge → TTS pipeline completed; includes per-stage latencies |
| `arc.voice.turn.failed` | `VoiceTurnFailedEvent` | Pipeline stage failed; includes error type and message |

**VoiceTurnCompletedEvent payload:**

```json
{
  "session_id": "sess-uuid",
  "room_id": "room-uuid",
  "correlation_id": "corr-uuid",
  "timestamp": "2026-03-10T12:00:00Z",
  "transcript": "What is the weather today?",
  "response_preview": "The weather in your area is ...",
  "stt_latency_ms": 420.0,
  "bridge_latency_ms": 880.0,
  "tts_latency_ms": 195.0,
  "total_latency_ms": 1495.0
}
```
