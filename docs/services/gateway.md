---
url: /arc-platform/docs/services/gateway.md
---
# Gateway (Heimdall)

> **Status:** Active | **Port:** 80, 8090 | **Profile:** think, reason, ultra-instinct

The `arc-gateway` service (Heimdall) is the platform API gateway built on Traefik. It routes all inbound HTTP traffic to the correct service and exposes a dashboard for live traffic inspection.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-gateway:latest` |
| Port(s) | 80 (HTTP), 8090 (admin/dashboard) |
| Health | `http://localhost:8090/health` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make gateway-up` | Start the service |
| `make gateway-down` | Stop the service |
| `make gateway-health` | Check health |
| `make gateway-logs` | Tail service logs |
