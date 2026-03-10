---
url: /arc-platform/docs/services/friday.md
---
# Observability (Friday / Friday Collector)

> **Status:** Active | **Port:** 3301, 8080, 4317 | **Profile:** see below

The observability stack consists of two separately profiled components:

* **Friday Collector** — OpenTelemetry Collector that receives OTLP traces and metrics from all services
* **Friday** — SigNoz UI (backed by ClickHouse) for trace browsing, dashboards, and alerting

## Quick Reference

| Component | Image | Port(s) | Health | Profile |
|-----------|-------|---------|--------|---------|
| Friday Collector | `ghcr.io/arc-framework/arc-friday-collector:latest` | 4317 (OTLP gRPC) | `http://localhost:13133/` | think, reason, ultra-instinct (core) |
| Friday (SigNoz UI) | `ghcr.io/arc-framework/arc-friday:latest` | 3301 (UI), 8080 (API) | `http://localhost:3301` | ultra-instinct (observe capability); also available in the `observe` dev profile |

## Make Targets

| Target | Description |
|--------|-------------|
| `make otel-up` | Start the full SigNoz + ClickHouse stack |
| `make otel-down` | Stop the full SigNoz + ClickHouse stack |
| `make otel-health` | Check health of the SigNoz stack |
| `make otel-logs` | Tail SigNoz + ClickHouse logs |
| `make friday-collector-up` | Start only the OTEL Collector |
| `make friday-collector-down` | Stop only the OTEL Collector |
