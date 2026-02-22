# syntax=docker/dockerfile:1.7
# ── Builder ──────────────────────────────────────────────────────────────────
FROM golang:1.24-alpine AS builder

WORKDIR /build

# Download dependencies first — cached as a separate layer until go.mod/go.sum change.
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Build — module and compiler caches persist between builds on the same host.
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o cortex ./cmd/cortex

# ── Final ─────────────────────────────────────────────────────────────────────
FROM alpine:3.21

RUN addgroup -S cortex && adduser -S -G cortex cortex

WORKDIR /app
COPY --from=builder --chown=cortex:cortex /build/cortex /usr/local/bin/cortex

EXPOSE 8081
USER cortex
ENTRYPOINT ["/usr/local/bin/cortex"]
CMD ["server"]
