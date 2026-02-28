FROM redis:alpine

LABEL org.opencontainers.image.title="ARC Sonic — Cache"
LABEL org.opencontainers.image.description="Redis cache and session store for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-sonic"
LABEL arc.service.codename="sonic"
LABEL arc.service.tech="redis"

# redis user (uid 999) exists in the upstream alpine image
# Switch to the redis user for non-root operation (NFR-1)
USER redis
