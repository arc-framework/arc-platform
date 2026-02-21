FROM signoz/signoz:v0.112.0

LABEL org.opencontainers.image.title="ARC Friday — Observability"
LABEL org.opencontainers.image.description="SigNoz query service and UI for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL com.arc.codename="friday"
LABEL com.arc.role="observability"

# Bake in the Prometheus config — no runtime volume mount required
COPY config/prometheus.yml /root/config/prometheus.yml
