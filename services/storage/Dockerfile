FROM minio/minio

LABEL org.opencontainers.image.title="ARC Tardis — Object Storage"
LABEL org.opencontainers.image.description="MinIO S3-compatible object storage for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-storage"
LABEL arc.service.codename="tardis"
LABEL arc.service.tech="minio"

# uid: minio/minio runs as root by default. We pre-create /data owned by uid 1000
# so the named volume mount initialises with correct permissions (see docker-compose user:).
USER root
RUN mkdir -p /data && chown 1000:1000 /data
USER 1000
