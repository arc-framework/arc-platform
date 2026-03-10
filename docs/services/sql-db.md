---
url: /arc-platform/docs/services/sql-db.md
---
# SQL Database (Oracle)

> **Status:** Active | **Port:** 5432 | **Profile:** think, reason, ultra-instinct

The `arc-persistence` service (Oracle) is the platform relational database built on PostgreSQL 17 with the pgvector extension. It serves as long-term memory storage for agents and provides vector similarity search until a dedicated vector service is available.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-persistence:latest` |
| Port(s) | 5432 |
| Health | `pg_isready -h localhost -p 5432` |
| Profile(s) | think, reason, ultra-instinct (core) |

> **Note:** The Make target prefix is `persistence` (e.g. `make persistence-up`), matching the image name `arc-persistence`.

## Make Targets

| Target | Description |
|--------|-------------|
| `make persistence-up` | Start the service |
| `make persistence-down` | Stop the service |
| `make persistence-health` | Check health |
| `make persistence-logs` | Tail service logs |
