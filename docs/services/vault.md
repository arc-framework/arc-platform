# Secrets (Nick Fury)

> **Status:** Active | **Port:** 8200 | **Profile:** ultra-instinct

Nick Fury is the platform secrets manager built on OpenBao. It provides dynamic secrets, encryption-as-a-service, and a secrets leasing API for platform services.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-vault:latest` |
| Port(s) | 8200 |
| Health | `http://localhost:8200/v1/sys/health` |
| Profile(s) | ultra-instinct (security capability) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make vault-up` | Start the service |
| `make vault-down` | Stop the service |
| `make vault-health` | Check health |
| `make vault-logs` | Tail service logs |
