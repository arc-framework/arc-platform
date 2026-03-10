---
url: /arc-platform/docs/contributing/new-service.md
---
# Adding a New Service

Follow these seven steps in order. Each step has a concrete acceptance criterion you can verify
locally before moving to the next.

## Checklist

### 1. Create `services/<name>/` with the standard structure

```
services/<name>/
├── service.yaml        # service metadata (see step 3)
├── Dockerfile          # container image (see step 2)
└── src/                # service source code
```

The directory name is the **role name** — lowercase, kebab-case (e.g., `services/my-worker/`). The
human-readable codename lives in `service.yaml`.

### 2. Add a `Dockerfile` (non-root user, multi-stage for Python/Go services)

Use a multi-stage build so the runtime image stays small and does not include build tools.

**Python example:**

```dockerfile
# ── build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/
# Non-root user — required by Constitution §VIII
RUN adduser --disabled-password --gecos "" appuser
USER appuser
EXPOSE 8800
CMD ["python", "-m", "src.main"]
```

**Go example:**

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /bin/service ./cmd/service

FROM gcr.io/distroless/static-debian12
COPY --from=builder /bin/service /service
USER nonroot:nonroot
EXPOSE 8800
ENTRYPOINT ["/service"]
```

### 3. Create `services/<name>/service.yaml` with `name`, `image`, `port`, `healthcheck`

```yaml
name: my-worker          # role name — matches directory
codename: Catalyst       # human-readable codename
image: arc-my-worker
port: 8800
healthcheck:
  path: /health
  interval: 10s
  timeout: 3s
  retries: 3
```

The `image` field is the GHCR image name without the registry prefix
(`ghcr.io/arc-framework/<image>`).

### 4. Add to `services/profiles.yaml` under the appropriate capability or core

If the service is general-purpose infrastructure needed by multiple capabilities, add it to `core`.
Otherwise, create or extend a capability entry:

```yaml
capabilities:
  my-capability:
    services: [my-worker]
    description: "Short description of what this capability provides"
```

If the capability should be part of a tier preset, add it to the relevant tier(s) under the
`# Tier Presets` section.

### 5. Add a CI workflow `.github/workflows/<name>-images.yml` for Docker build/push

Copy the pattern from an existing workflow (e.g., `.github/workflows/voice-images.yml`). At
minimum the workflow must:

* Trigger on `push` to `main` when files under `services/<name>/` change
* Build the Docker image with `docker buildx build`
* Push to `ghcr.io/arc-framework/arc-<name>` tagged with the commit SHA and `latest`
* Run on pull requests in build-only mode (no push)

### 6. Add a docs page and update the sidebar

Create `docs/services/<name>.md` with at minimum:

* Codename, role, port, health URL
* Tier/capability membership
* `make` targets for up, down, health, logs

Then add the page to the Services sidebar in `docs/.vitepress/config.ts`.

### 7. Add a health check: `GET /health` returning `{"status": "ok"}` with HTTP 200

Every service must expose a `/health` endpoint that returns HTTP 200 with a JSON body
`{"status": "ok"}`. This endpoint is polled by `make dev-health` and by Docker Compose
`healthcheck`.

For FastAPI services:

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

For Go services using `net/http`:

```go
mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    _, _ = w.Write([]byte(`{"status":"ok"}`))
})
```
