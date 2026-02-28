FROM signoz/signoz-otel-collector:v0.142.0

LABEL org.opencontainers.image.title="ARC Friday Collector — Telemetry"
LABEL org.opencontainers.image.description="OTEL Collector for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL com.arc.codename="friday-collector"
LABEL com.arc.role="telemetry"

# Bake in collector config — no runtime volume mounts required
COPY config/otel-collector-config.yaml /etc/otelcol/config.yaml
COPY config/otel-collector-opamp-config.yaml /etc/otelcol/manager-config.yaml
