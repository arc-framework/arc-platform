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

# ── Stage 2: AsyncAPI HTML builder ────────────────────────────────────────────
FROM node:20-slim AS async-docs-builder

WORKDIR /docs

COPY contracts/asyncapi.yaml ./asyncapi.yaml

# Generate static HTML from AsyncAPI spec (optional — served when SHERLOCK_ASYNC_DOCS_ENABLED=true)
# Falls back to an empty directory if template install or generation fails.
# @asyncapi/html-template@2.x requires generator >=1.15.0 <2.0.0 (matches bundled 1.17.25)
RUN mkdir -p /async-docs-build && \
    (npx --yes @asyncapi/cli generate fromTemplate asyncapi.yaml \
        @asyncapi/html-template@2 -o /async-docs-build --force-write --no-interactive \
        || echo "AsyncAPI docs generation skipped")

# ── Stage 3: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim

# Non-root user (constitution VIII — security by default)
# -m creates /home/sherlock — required by sentence-transformers HF model cache
RUN groupadd -r sherlock && useradd -r -g sherlock -m -d /home/sherlock sherlock

WORKDIR /app

COPY --from=builder --chown=sherlock:sherlock /install /usr/local
COPY --from=builder --chown=sherlock:sherlock /build/src ./src

# Copy AsyncAPI HTML docs (served at /async-docs when SHERLOCK_ASYNC_DOCS_ENABLED=true)
COPY --from=async-docs-builder --chown=sherlock:sherlock /async-docs-build ./async-docs

EXPOSE 8000

USER sherlock

CMD ["uvicorn", "sherlock.main:app", "--host", "0.0.0.0", "--port", "8000"]
