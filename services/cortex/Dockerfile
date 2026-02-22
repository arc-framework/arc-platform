# ── Builder ──────────────────────────────────────────────────────────────────
FROM golang:1.24-alpine AS builder

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o cortex ./cmd/cortex

# ── Final ─────────────────────────────────────────────────────────────────────
FROM alpine:3.21

RUN addgroup -S cortex && adduser -S -G cortex cortex

WORKDIR /app
COPY --from=builder --chown=cortex:cortex /build/cortex /usr/local/bin/cortex

EXPOSE 8081
USER cortex
ENTRYPOINT ["/usr/local/bin/cortex"]
CMD ["server"]
