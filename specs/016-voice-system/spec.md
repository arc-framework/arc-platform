# Feature: Voice System

> **Spec**: 016-voice-system
> **Author**: arc-framework
> **Date**: 2026-03-06
> **Status**: Draft
> **ARD**: `docs/ard/VOICE-SYSTEM.md`
> **HLD**: `docs/ard/VOICE-HLD.md`
> **Framework**: `docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md`

## Executive Summary

Build `services/voice/` as ARC's production voice orchestration service. `arc-voice-agent` will expose OpenAI-compatible STT and TTS APIs, run a LiveKit worker for room-based audio-to-audio sessions, bridge voice turns into `arc-reasoner` instead of duplicating reasoning, and publish durable voice lifecycle events for analytics, billing, and compliance. Existing realtime infrastructure in `services/realtime/` becomes a dependency, not the feature itself.

## Target Modules

| Module    | Path                                                | Impact                                           |
| --------- | --------------------------------------------------- | ------------------------------------------------ |
| Services  | `services/voice/`                                   | New — `arc-voice-agent` production voice service |
| Services  | `services/profiles.yaml`                            | Update — add `voice` to `reason` profile         |
| Services  | `services/realtime/`                                | Existing dependency — no new transport design    |
| Contracts | `services/voice/contracts/`                         | New — OpenAPI + AsyncAPI                         |
| CI/CD     | `.github/workflows/`                                | New — voice image and release workflows          |
| Docs      | `docs/ard/VOICE-SYSTEM.md`, `docs/ard/VOICE-HLD.md` | New/updated architecture docs                    |

## Framework Alignment

This feature implements the voice slice of the ARC enterprise framework:

- It realizes the framework's **sync flow for chat / voice**.
- It preserves the **REST + async topic** contract model.
- It keeps **`arc-reasoner` as the only reasoning brain**.
- It lets teams run voice as a **sidecar** against existing infrastructure or as part of the full `reason` profile.

## User Stories

### Story 1 — REST speech APIs

As an application developer, I want OpenAI-compatible STT and TTS endpoints so that existing clients can add speech support without custom adapters.

**Acceptance Criteria**

- `POST /v1/audio/transcriptions` accepts multipart audio and returns transcript text with language and duration metadata.
- `POST /v1/audio/speech` accepts JSON text input and returns a WAV stream with duration and sample-rate headers.
- Default providers are local-first and work without external accounts.
- Invalid files, unsupported formats, and provider failures return typed error responses.

### Story 2 — Realtime voice agent

As an end user, I want to talk to ARC in a realtime room so that I can have low-latency spoken conversations with the same reasoning system used for chat.

**Acceptance Criteria**

- `arc-voice-agent` joins `arc-realtime` rooms as a worker and processes turns with VAD → STT → `arc-reasoner` → TTS.
- `arc-voice-agent` uses `arc-reasoner` for reasoning and does not embed an independent LLM path.
- End-to-end turn latency target remains within the documented budget of roughly 750–1550 ms.
- Room-level failures publish a durable failure event and are visible in logs and traces.

### Story 3 — Durable platform events

As a platform operator, I want durable voice session and turn events so that analytics, billing, and compliance can subscribe without coupling to Scarlett internals.

**Acceptance Criteria**

- `arc-voice-agent` publishes `arc.voice.session.started`, `arc.voice.session.ended`, `arc.voice.turn.completed`, and `arc.voice.turn.failed`.
- Event schemas are documented in `contracts/asyncapi.yaml`.
- Events include correlation identifiers, room/session metadata, duration/latency fields, and provider outcome data.
- Event publishing failure does not break the low-latency room response path.

### Story 4 — Offline-first deployment

As a platform team, I want voice to work locally with no external speech vendors so that ARC stays aligned with the local-first constitution.

**Acceptance Criteria**

- Default STT provider is `faster-whisper`.
- Default TTS provider is `piper`.
- Cloud providers are optional adapters behind interfaces.
- The service boots in the `reason` profile with no required cloud credentials.

## Requirements

### Functional

- [ ] FR-1: Create `services/voice/` with `service.yaml`, `Dockerfile`, `pyproject.toml`, contracts, and `src/voice/` package.
- [ ] FR-2: Implement `POST /v1/audio/transcriptions` with provider abstraction and OpenAI-compatible response shape. Authentication is delegated to Heimdall (arc-gateway); standalone deployments without Heimdall must enforce bearer token validation separately.
- [ ] FR-3: Implement `POST /v1/audio/speech` with provider abstraction and WAV streaming response. Authentication is delegated to Heimdall (arc-gateway); standalone deployments without Heimdall must enforce bearer token validation separately.
- [ ] FR-4: Implement `GET /health` and `GET /health/deep` for shallow and dependency-aware checks.
- [ ] FR-5: Start a LiveKit worker inside `arc-voice-agent` and join `arc-realtime` rooms for audio-to-audio sessions.
- [ ] FR-6: Bridge voice turns to `arc-reasoner` over a configurable `arc-messaging` subject; default to `reasoner.request`.
- [ ] FR-7: Publish durable voice events on `arc-streaming` for session lifecycle and turn outcomes.
- [ ] FR-8: Add `services/voice/contracts/openapi.yaml` and `services/voice/contracts/asyncapi.yaml`.
- [ ] FR-9: Add `voice` to the `reason` profile in `services/profiles.yaml`.
- [ ] FR-10: Add observability with OTEL metrics, traces, and structured logs.
- [ ] FR-11: Add CI/release workflows for the voice image.
- [ ] FR-12: Reuse existing realtime infrastructure in `services/realtime/`; do not introduce a second transport stack.

### Non-Functional

- [ ] NFR-1: `arc-voice-agent` runs as a non-root container and follows the standard service packaging pattern.
- [ ] NFR-2: Default deployment works without external speech vendor credentials.
- [ ] NFR-3: `GET /health` responds when the process is alive; `GET /health/deep` checks `arc-realtime` and `arc-messaging` connectivity and reports degraded status clearly.
- [ ] NFR-4: OTEL captures per-turn latency for STT, Sherlock bridge, TTS, and total pipeline time.
- [ ] NFR-5: Session and turn events never contain secrets or raw full-audio payloads.
- [ ] NFR-6: The public async contract uses `arc-streaming` topics even though internal speed-path requests use `arc-messaging`.
- [ ] NFR-7: The service passes `ruff`, `mypy`, and `pytest` following the same Python standards as `arc-reasoner`.
- [ ] NFR-8: Voice events are published to `arc-streaming` with a 7-day default Pulsar retention policy. Platform operators may configure longer retention for compliance or billing audit requirements.

## Key Entities

| Entity                | Description                                                             |
| --------------------- | ----------------------------------------------------------------------- |
| `VoiceSession`        | LiveKit room participation and lifecycle metadata                       |
| `VoiceTurn`           | Single user utterance plus agent response metrics                       |
| `STTPort`             | Protocol interface for transcription providers                          |
| `TTSPort`             | Protocol interface for synthesis providers                              |
| `LLMBridgePort`       | Protocol interface for `arc-voice-agent` ↔ `arc-reasoner` turn exchange |
| `VoiceSessionStarted` | Durable async event for room/session start                              |
| `VoiceTurnCompleted`  | Durable async event for successful turn completion                      |

## Out of Scope

- Browser or mobile SDK implementation
- New realtime transport infrastructure beyond the already implemented LiveKit stack
- Training or fine-tuning speech models
- Enterprise telephony connectors beyond the base room and REST capabilities
- Replacing `arc-reasoner` with a separate voice-native reasoning engine

## Dependencies

- Existing realtime transport in `services/realtime/`
- `arc-reasoner` request/reply contracts in `services/reasoner/`
- `arc-messaging` for low-latency internal turn exchange
- `arc-streaming` for durable async voice events
- `arc-cache` and `arc-storage` for optional session state and recording support
- Architecture guidance in `docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md`

## Edge Cases

| Scenario                                           | Expected Behavior                                                              |
| -------------------------------------------------- | ------------------------------------------------------------------------------ |
| `arc-realtime` unavailable                         | REST APIs still boot; room mode reports degraded/unavailable                   |
| `arc-messaging` unavailable                        | `health/deep` fails; room turns fail fast with typed error and failure event   |
| `arc-cache` unavailable                            | Room mode continues without cached hot state                                   |
| `arc-storage` or `arc-realtime-egress` unavailable | Sessions continue; recording/export features degrade gracefully                |
| Local speech model cold start                      | First request is slower, but service remains healthy and emits latency metrics |
| Subject naming migration to `arc.reasoner.request` | `arc-voice-agent` changes by config, not by code rewrite                       |

## Success Criteria

- [ ] SC-1: `services/voice/` boots successfully in the `reason` profile.
- [ ] SC-2: `POST /v1/audio/transcriptions` returns valid transcript metadata for supported audio formats.
- [ ] SC-3: `POST /v1/audio/speech` streams playable WAV audio.
- [ ] SC-4: `arc-voice-agent` joins an `arc-realtime` room and completes a full spoken turn through `arc-reasoner`.
- [ ] SC-5: Voice session and turn events are emitted on `arc-streaming` with valid schema payloads.
- [ ] SC-6: OTEL traces show STT, `arc-reasoner` bridge, and TTS spans per turn.
- [ ] SC-7: Default local providers work without cloud credentials.

## Docs & Links Update

- [ ] Create `docs/ard/VOICE-SYSTEM.md`
- [ ] Update `docs/ard/VOICE-HLD.md`
- [ ] Link the voice docs back to `docs/ard/ARC-ENTERPRISE-AI-FRAMEWORK.md`
- [ ] Add a docs update task for service references and profile documentation

## Constitution Compliance

| Principle             | Applies | Status  | Notes                                                                                         |
| --------------------- | ------- | ------- | --------------------------------------------------------------------------------------------- |
| I. Zero-Dep CLI       | [ ]     | n/a     | No CLI runtime change                                                                         |
| II. Platform-in-a-Box | [x]     | WARNING | Voice is intentionally `reason` profile only because model footprint is too heavy for `think` |
| III. Modular Services | [x]     | PASS    | `services/voice/` is self-contained and depends on existing platform services                 |
| IV. Two-Brain         | [x]     | PASS    | Python owns speech intelligence; Go infra remains unchanged                                   |
| V. Polyglot Standards | [x]     | PASS    | FastAPI + ruff + mypy + pytest                                                                |
| VI. Local-First       | [x]     | PASS    | Whisper + Piper are default providers                                                         |
| VII. Observability    | [x]     | PASS    | OTEL metrics, traces, and health endpoints are required                                       |
| VIII. Security        | [x]     | PASS    | Non-root container, no secrets in logs or events                                              |
| IX. Declarative       | [x]     | PASS    | Contracts and service metadata are explicit                                                   |
| X. Stateful Ops       | [x]     | PASS    | Session state and lifecycle events are queryable through platform dependencies                |
| XI. Resilience        | [x]     | PASS    | Graceful degradation for storage/cache and failure events for runtime issues                  |
| XII. Interactive      | [ ]     | n/a     | No TUI scope                                                                                  |
