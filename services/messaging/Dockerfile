FROM nats:alpine

LABEL org.opencontainers.image.title="ARC Flash — Messaging"
LABEL org.opencontainers.image.description="NATS + JetStream broker for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-messaging"
LABEL arc.service.codename="flash"
LABEL arc.service.tech="nats"

# Pre-create the JetStream store directory owned by the nats user (uid 1000).
# Without this, the named volume mount is root-owned and nats cannot write to it.
USER root
RUN mkdir -p /data && chown 1000:1000 /data

# nats user (uid 1000) already exists in the upstream image
USER 1000
