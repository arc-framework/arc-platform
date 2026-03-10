# syntax=docker/dockerfile:1.7
# ── Stage 1: Python builder ────────────────────────────────────────────────────
# Uses arc-reasoner-base which pre-bakes torch, sentence-transformers, and
# pulsar-client — the slow wheels that dominate build time on a cold cache miss.
# Base is rebuilt only when those heavy deps change (see Dockerfile.base).
#
# To test locally before the base image is pushed to GHCR:
#   docker buildx build --platform linux/amd64 \
#     -f services/reasoner/Dockerfile.base \
#     -t arc-reasoner-base:local services/reasoner/
#   docker build --build-arg BASE=arc-reasoner-base:local \
#     -f services/reasoner/Dockerfile services/reasoner/
ARG BASE=ghcr.io/arc-framework/arc-reasoner-base:latest
FROM ${BASE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy only the manifest first — remaining deps re-install only when pyproject.toml changes.
COPY pyproject.toml ./

# Stub package init allows setuptools to resolve the package name during
# dependency resolution before the full source tree is copied in.
RUN mkdir -p src/reasoner && touch src/reasoner/__init__.py

# Seed /install with the heavy packages already in the base (torch, sentence-transformers,
# pulsar-client and all their transitive deps including click, huggingface-hub, etc.).
# pip then sees them as satisfied in the prefix and skips re-downloading them —
# only the remaining lightweight deps (fastapi, uvicorn, langchain, etc.) are fetched.
# Stage 2 starts from python:3.13-slim and only gets /install, so it inherits everything.
RUN PY=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") && \
    mkdir -p /install/lib/python${PY}/site-packages /install/bin && \
    cp -a /usr/local/lib/python${PY}/site-packages/. /install/lib/python${PY}/site-packages/

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install --no-compile .

# Copy actual source after deps are cached — source changes hit only the fast
# install below.
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install --no-compile --no-deps --upgrade .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# AsyncAPI HTML docs are NOT generated at build time — the npx download adds
# 10+ minutes to every CI build for an optional feature. The service falls back
# to a 404 JSON when /app/async-docs does not exist (see main.py lifespan). To
# serve the docs locally, run:
#   npx @asyncapi/generator@1 contracts/asyncapi.yaml \
#       @asyncapi/html-template@2 -o async-docs --force-write --no-interactive
# Note: @asyncapi/cli v2+ bundles generator v3 which is incompatible with
# html-template@2.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/reasoner

# Non-root user (constitution VIII — security by default)
# -m creates /home/reasoner — required by sentence-transformers HF model cache.
RUN groupadd -r reasoner && useradd -r -g reasoner -m -d /home/reasoner reasoner

WORKDIR /app

COPY --from=builder --chown=reasoner:reasoner /install /usr/local

EXPOSE 8000

USER reasoner

CMD ["uvicorn", "reasoner.main:app", "--host", "0.0.0.0", "--port", "8000"]
