---
url: /arc-platform/docs/services/storage.md
---
# Object Storage (Tardis)

> **Status:** Active | **Port:** 9000, 9001 | **Profile:** ultra-instinct

The `arc-storage` service (Tardis) is the platform object storage service built on MinIO. It provides S3-compatible blob storage for artifacts, model weights, and large binary assets.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-storage:latest` |
| Port(s) | 9000 (API), 9001 (console) |
| Health | `http://localhost:9000/minio/health/live` |
| Profile(s) | ultra-instinct (storage capability) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make storage-up` | Start the service |
| `make storage-down` | Stop the service |
| `make storage-health` | Check health |
| `make storage-logs` | Tail service logs |
