# syntax=docker/dockerfile:1.7
# ── Stage 1: Python builder ────────────────────────────────────────────────────
# python:3.13-slim (Debian): pre-built wheels are available for pulsar-client
# and faster-whisper — Alpine musl toolchain is insufficient.
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# gcc: needed to compile C extensions (e.g. faster-whisper native bindings)
# curl: used to download the piper release binary
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install piper TTS binary from upstream release.
# The binary is statically linked — no shared-lib dependencies in the runtime image.
# Piper uses Linux kernel arch names (x86_64, aarch64) not Docker's TARGETARCH names (amd64, arm64).
ARG PIPER_VERSION=2023.11.14-2
ARG TARGETARCH
RUN case "${TARGETARCH}" in \
      amd64) PIPER_ARCH=x86_64  ;; \
      arm64) PIPER_ARCH=aarch64 ;; \
      arm)   PIPER_ARCH=armv7l  ;; \
      *)     echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_${PIPER_ARCH}.tar.gz" \
    | tar -xz -C /tmp \
    && install -m 0755 /tmp/piper/piper /usr/local/bin/piper

WORKDIR /build

# Copy only the manifest first — dependencies are only re-installed when
# pyproject.toml changes.
COPY pyproject.toml ./

# Stub package init allows setuptools to resolve the package name during
# dependency resolution before the full source tree is copied in.
RUN mkdir -p src/voice && touch src/voice/__init__.py

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install --no-compile .

# Copy actual source after deps are cached — source changes hit only the fast
# install below.
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --prefix=/install --no-compile --no-deps --upgrade .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/scarlett

# Non-root user (constitution VIII — security by default)
RUN groupadd -r scarlett && useradd -r -g scarlett -m -d /home/scarlett scarlett

WORKDIR /app

COPY --from=builder --chown=scarlett:scarlett /install /usr/local
# Carry the piper binary into the runtime image
# Root-owned so it stays in /usr/local/bin alongside system binaries; 0755 lets scarlett execute it.
COPY --from=builder --chown=root:root /usr/local/bin/piper /usr/local/bin/piper

EXPOSE 8803

USER scarlett

CMD ["uvicorn", "voice.main:app", "--host", "0.0.0.0", "--port", "8803"]
