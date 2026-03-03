# ── Stage 1: Python builder ────────────────────────────────────────────────────
# python:3.13-slim (Debian): pre-built wheels available for pulsar-client,
# sentence-transformers (torch), and asyncpg — Alpine musl toolchain is insufficient.
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --prefix=/install --no-cache-dir ".[dev]" \
    && pip install --prefix=/install --no-cache-dir -e . --no-deps

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# AsyncAPI HTML docs are NOT generated at build time — the npx download adds 10+ minutes
# to every CI build for an optional feature. The service falls back to a 404 JSON when
# /app/async-docs does not exist (see main.py lifespan). To serve the docs locally,
# run: npx @asyncapi/cli generate fromTemplate contracts/asyncapi.yaml
#          @asyncapi/html-template@2 -o async-docs --force-write --no-interactive
FROM python:3.13-slim

# Non-root user (constitution VIII — security by default)
# -m creates /home/sherlock — required by sentence-transformers HF model cache
RUN groupadd -r sherlock && useradd -r -g sherlock -m -d /home/sherlock sherlock

WORKDIR /app

COPY --from=builder --chown=sherlock:sherlock /install /usr/local
COPY --from=builder --chown=sherlock:sherlock /build/src ./src

EXPOSE 8000

USER sherlock

CMD ["uvicorn", "sherlock.main:app", "--host", "0.0.0.0", "--port", "8000"]
