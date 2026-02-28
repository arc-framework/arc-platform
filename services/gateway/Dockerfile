FROM traefik:v3

LABEL org.opencontainers.image.title="ARC Heimdall — API Gateway"
LABEL org.opencontainers.image.description="Traefik v3 ingress gateway for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-gateway"
LABEL arc.service.codename="heimdall"
LABEL arc.service.tech="traefik"

# Traefik listens on non-privileged internal ports (8080 for proxy, 8090 for dashboard).
# Host port 80 maps from container port 8080 — Traefik never binds a privileged port inside
# the container, so uid 1000 is safe.
USER 1000
