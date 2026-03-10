# Feature Flags (Mystique)

> **Status:** Active | **Port:** 4242 | **Profile:** ultra-instinct

The `arc-flags` service (Mystique) is the platform feature-flag service built on Unleash. It enables runtime toggling of platform capabilities without redeployment.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-flags:latest` |
| Port(s) | 4242 |
| Health | `http://localhost:4242/health` |
| Profile(s) | ultra-instinct (security capability) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make flags-up` | Start the service |
| `make flags-down` | Stop the service |
| `make flags-health` | Check health |
| `make flags-logs` | Tail service logs |
