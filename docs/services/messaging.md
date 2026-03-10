# Messaging (Flash)

> **Status:** Active | **Port:** 4222, 8222 | **Profile:** think, reason, ultra-instinct

Flash is the platform message broker built on NATS. It carries low-latency, at-most-once messages between platform services and agent workers.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-messaging:latest` |
| Port(s) | 4222 (client), 8222 (monitoring) |
| Health | `http://localhost:8222/healthz` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make messaging-up` | Start the service |
| `make messaging-down` | Stop the service |
| `make messaging-health` | Check health |
| `make messaging-logs` | Tail service logs |
