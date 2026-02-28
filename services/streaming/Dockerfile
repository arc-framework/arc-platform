FROM apachepulsar/pulsar:latest

LABEL org.opencontainers.image.title="ARC Dr. Strange — Streaming"
LABEL org.opencontainers.image.description="Apache Pulsar standalone broker for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-strange"
LABEL arc.service.codename="strange"
LABEL arc.service.tech="pulsar"

# NOTE: apachepulsar/pulsar requires root to initialize /pulsar on first run.
# Non-root is not supported upstream — documented deviation from NFR-1.
# See: https://github.com/apache/pulsar/issues/8284
