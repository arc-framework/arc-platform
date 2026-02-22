# Observability — Friday (SigNoz)

SigNoz observability stack: query service + ClickHouse (signal store) + ZooKeeper (ClickHouse coordination).

## Prerequisites

- **Docker Desktop**: ≥ 4 GB RAM allocated to Docker (ClickHouse minimum)
  - macOS: Docker Desktop → Settings → Resources → Memory → set to 4 GB or more

## Quickstart

```bash
# From repo root — starts the full stack (telemetry + observability)
make otel-up

# Observability stack only (no OTEL collector)
make otel-up-observability
```

## UI

```
http://localhost:3301
```

SigNoz UI is bound to `127.0.0.1` only and is not accessible from other machines on the network.

## Health Check

```bash
curl -sf http://localhost:3301/api/v1/health
```

Returns HTTP 200 when SigNoz is running and connected to ClickHouse.

```bash
# Check both health endpoints at once
make otel-health
```

## Network Security

| Service | Host Exposure |
|---------|--------------|
| SigNoz  | `127.0.0.1:3301` only |
| ClickHouse | Not exposed — internal Docker network only |
| ZooKeeper  | Not exposed — internal Docker network only |

ClickHouse and ZooKeeper communicate over the shared `arc_otel_net` Docker network. They are not accessible from the host machine.

## Stack Management

```bash
make otel-up      # start full stack
make otel-down    # stop and remove all containers
make otel-ps      # show container status
make otel-logs    # stream logs from all OTEL containers
make otel-health  # probe both health endpoints
```
