# syntax=docker/dockerfile:1.7
# ── Stage 1: Python builder ────────────────────────────────────────────────────
# python:3.13-slim (Debian): pre-built wheels are available for pulsar-client,
# sentence-transformers (torch), and asyncpg — Alpine musl toolchain is insufficient.
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only the manifest first — dependencies are only re-installed when
# pyproject.toml changes.
COPY pyproject.toml ./

# Stub package init allows setuptools to resolve the package name during
# dependency resolution before the full source tree is copied in.
RUN mkdir -p src/reasoner && touch src/reasoner/__init__.py

# Install CPU-only PyTorch first — prevents pip from pulling the CUDA variant.
# Keep the builder production-only: dev/test tooling does not belong in the
# runtime image and adds significant build time and size.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install --no-compile \
      torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --prefix=/install --no-compile .

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
