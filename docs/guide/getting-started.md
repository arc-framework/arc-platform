---
url: /arc-platform/docs/guide/getting-started.md
---
# Getting Started

This guide takes you from a fresh clone to a running A.R.C. Platform with verified service health.

## Prerequisites

Before you begin, install the following tools:

| Tool | Version | Purpose |
|------|---------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 24+ (with Compose v2) | Container runtime for all platform services |
| [`arc` CLI](https://github.com/arc-framework/arc-cli) | latest | Workspace management and service orchestration |
| [`gh` CLI](https://cli.github.com/) | 2.x | GitHub operations (required for `make publish-all`) |
| [Node.js](https://nodejs.org/) | 18+ | Only needed to run the docs site locally |

Verify your setup:

```bash
docker --version          # Docker version 24.x.x
docker compose version    # Docker Compose version v2.x.x
arc version               # arc version vX.Y.Z
gh --version              # gh version 2.x.x
```

## Fork and Clone the Repository

Fork the repository on GitHub, then clone your fork:

```bash
gh repo fork arc-framework/arc-platform --clone --remote
cd arc-platform
```

This adds both `origin` (your fork) and `upstream` (arc-framework/arc-platform) as remotes.

If you want a direct clone without forking:

```bash
git clone https://github.com/arc-framework/arc-platform.git
cd arc-platform
```

## Initialize the Workspace

Run `arc workspace init` to create your `arc.yaml` manifest. This command prompts for a tier and writes the file to the repository root.

```bash
arc workspace init
```

Example session:

```
? Select a platform tier:
  > think       — core infrastructure only, fastest to start
    reason      — core + reasoning engine (LLM)
    ultra-instinct — full platform, all capabilities

Workspace initialized: arc.yaml
```

You can also pass flags to skip the prompt:

```bash
arc workspace init --tier think
```

The generated `arc.yaml` looks like this:

```yaml
version: "1.0.0"
tier: "think"
capabilities: []
```

## Start the Platform

Start all services for the `think` tier with:

```bash
arc run --profile think
```

The CLI resolves services from `services/profiles.yaml`, renders a Docker Compose file, and calls `docker compose up` in detached mode. On first run, Docker pulls the required images — this may take a few minutes depending on your connection.

Expected output:

```
Starting arc-platform [think]
  core services: messaging, cache, streaming, cortex, persistence, gateway, friday-collector
Pulling images... done
Starting services... done

Platform is ready.
  Gateway:    http://localhost:80
  Cortex API: http://localhost:8801/health
```

## Verify Service Health

Once the platform is up, confirm all services are healthy:

```bash
make dev-health
```

Expected output (all services show `healthy`):

```
arc-gateway          healthy   http://localhost:8090/ping
arc-messaging        healthy   http://localhost:8222/healthz
arc-streaming        healthy   http://localhost:8082/admin/v2/brokers/health
arc-cache            healthy   (redis-cli ping → PONG)
arc-persistence      healthy   (pg_isready)
arc-cortex           healthy   http://localhost:8801/health
arc-friday-collector healthy   http://localhost:13133/
```

If any service shows `unhealthy` or `starting`, wait 10–15 seconds and re-run `make dev-health`. Most services need a moment to complete their own startup sequences.

## Stop the Platform

```bash
make dev-down
```

This stops and removes all containers started by the current profile. Persistent volumes are retained so your data survives restarts.

## Next Steps

* [Services](/services/) — ports, health URLs, and API references for every service
* [Contributing](/contributing/architecture) — architecture overview, conventions, and guides for adding new services and capabilities
* [LLM Testing](/guide/llm-testing) — `curl` examples for the reasoning engine and voice service
* [arc.yaml Reference](/guide/arc-yaml-reference) — full reference for the workspace manifest

## Troubleshooting

### Docker not running

Make sure Docker Desktop is started and the whale icon appears in your system tray. Verify with:

```bash
docker ps
```

### Port conflict

Another process is using a default port. Check which port is conflicting:

```bash
lsof -i :<PORT>
```

Then stop the conflicting process or change the port in your service override.

### Services failing health checks

Your machine may not have enough resources. Check with `docker stats`. Consider using the `think` profile (lightest) to start:

```bash
arc run --profile think
```

### Symlink issues on macOS (Apple Silicon)

If `docs/specs` shows as broken, ensure you cloned with symlink support:

```bash
git config core.symlinks true
git checkout .
```
