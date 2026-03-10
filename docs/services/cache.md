# Cache (Sonic)

> **Status:** Active | **Port:** 6379 | **Profile:** think, reason, ultra-instinct

The `arc-cache` service (Sonic) is the platform cache service built on Redis. It provides sub-millisecond key-value storage used for embedding caches, session state, and rate-limit counters.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-cache:latest` |
| Port(s) | 6379 |
| Health | `redis-cli -p 6379 ping` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make cache-up` | Start the service |
| `make cache-down` | Stop the service |
| `make cache-health` | Check health |
| `make cache-logs` | Tail service logs |
