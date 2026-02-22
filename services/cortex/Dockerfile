# syntax=docker/dockerfile:1.7
# ── Builder ──────────────────────────────────────────────────────────────────
FROM golang:1.24-alpine AS builder

WORKDIR /build

# Download dependencies first — cached as a separate layer until go.mod/go.sum change.
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source and generate Swagger docs, then compile.
# swag is installed here so the docs/ package (imported by server.go) is always
# generated from the in-tree annotations rather than shipped in the build context.
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go install github.com/swaggo/swag/cmd/swag@v1.16.4 && \
    swag init -g cmd/cortex/main.go -o docs --quiet && \
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
