FROM qdrant/qdrant

LABEL org.opencontainers.image.title="ARC Cerebro — Vector Search"
LABEL org.opencontainers.image.description="Qdrant vector database for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-cerebro"
LABEL arc.service.codename="cerebro"
LABEL arc.service.tech="qdrant"

# qdrant/qdrant runs as root (uid 0) by default. Pre-create all writable directories
# owned by uid 1000 so the named volume and working-dir writes succeed at runtime.
# Qdrant resolves storage_path and snapshots_path relative to /qdrant (working dir).
USER root
RUN mkdir -p /qdrant/storage /qdrant/snapshots && \
    chown -R 1000:1000 /qdrant/storage /qdrant/snapshots
USER 1000
