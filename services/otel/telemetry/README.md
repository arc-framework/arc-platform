# Telemetry — Friday Collector (signoz-otel-collector)

OTEL collector that accepts signals from any A.R.C. service and exports them to ClickHouse.

## Quickstart

```bash
# From repo root
make otel-up-telemetry
```

> **Note**: The full pipeline (traces visible in SigNoz) requires the observability stack to be running too. Use `make otel-up` to start both.

## Open Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 4317 | gRPC     | OTLP signal ingestion |
| 4318 | HTTP     | OTLP signal ingestion |
| 13133 | HTTP    | Health check (internal) |

All ports bound to `127.0.0.1` — not accessible from outside the host.

## Health Check

```bash
curl -sf http://localhost:13133/
```

Returns HTTP 200 when the collector is running and ready.

## Collector Config

Config lives at `config/otel-collector-config.yaml`.

| Section | Detail |
|---------|--------|
| **Receivers** | `otlp` — gRPC on `:4317`, HTTP on `:4318` |
| **Processors** | `batch` — buffers up to 10,000 spans before flushing |
| **Exporters** | `clickhousetraces` — writes to `arc-friday-clickhouse:9000` on the shared `arc_otel_net` Docker network |
| **Extensions** | `health_check` — HTTP probe on `:13133` |
| **Pipeline** | `traces`: otlp → batch → clickhousetraces |

To add metrics or logs pipelines, extend `otel-collector-config.yaml` — do not create per-service collector configs.
