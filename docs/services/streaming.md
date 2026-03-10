# Streaming (Dr. Strange)

> **Status:** Active | **Port:** 6650, 8082 | **Profile:** think, reason, ultra-instinct

Dr. Strange is the platform event streaming service built on Apache Pulsar. It provides durable, ordered, multi-consumer topic streams for high-throughput event pipelines.

## Quick Reference

| Field | Value |
|-------|-------|
| Image | `ghcr.io/arc-framework/arc-streaming:latest` |
| Port(s) | 6650 (broker), 8082 (admin) |
| Health | `http://localhost:8082/metrics` |
| Profile(s) | think, reason, ultra-instinct (core) |

## Make Targets

| Target | Description |
|--------|-------------|
| `make streaming-up` | Start the service |
| `make streaming-down` | Stop the service |
| `make streaming-health` | Check health |
| `make streaming-logs` | Tail service logs |
