# Realtime (Daredevil / Sentry / Scribe)

> **Status:** Active | **Port:** 7880, 7881, 7882 | **Profile:** ultra-instinct

The realtime layer is built on LiveKit and consists of three co-deployed services started as a single unit:

- **Daredevil** — LiveKit Server (WebRTC media routing)
- **Sentry** — LiveKit Ingress (inbound stream ingestion)
- **Scribe** — LiveKit Egress (outbound recording and forwarding)

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-realtime:latest` |
| Port(s) | 7880 (HTTP), 7881 (HTTPS), 7882 (WebRTC/TURN) |
| Health | `http://localhost:7880/` |
| Profile(s) | ultra-instinct (voice capability) |

> **Note:** `make realtime-up` starts all three containers (realtime-server, realtime-ingress, realtime-egress) together.

## Make Targets

| Target | Description |
|--------|-------------|
| `make realtime-up` | Start all three realtime services |
| `make realtime-down` | Stop all three realtime services |
| `make realtime-health` | Check health |
| `make realtime-logs` | Tail realtime service logs |
