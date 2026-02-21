FROM clickhouse/clickhouse-server:25.5.6

# TARGETARCH is injected by docker buildx for multi-arch builds (amd64 | arm64)
ARG TARGETARCH=amd64

LABEL org.opencontainers.image.title="ARC ClickHouse — Signal Store"
LABEL org.opencontainers.image.description="ClickHouse signal store for the A.R.C. Platform observability stack"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL com.arc.role="signal-store"

# Download histogramQuantile UDF at build time — no internet access needed at runtime.
# Stored at /opt/arc/user_scripts/ which is outside the data volume (/var/lib/clickhouse/)
# so the binary is never shadowed by a Docker volume mount.
RUN mkdir -p /opt/arc/user_scripts && \
    wget -O /tmp/hq.tar.gz \
      "https://github.com/SigNoz/signoz/releases/download/histogram-quantile%2Fv0.0.1/histogram-quantile_linux_${TARGETARCH}.tar.gz" && \
    tar -xvzf /tmp/hq.tar.gz -C /tmp && \
    mv /tmp/histogram-quantile /opt/arc/user_scripts/histogramQuantile && \
    chmod +x /opt/arc/user_scripts/histogramQuantile && \
    rm /tmp/hq.tar.gz

# Bake in all ClickHouse config files — no runtime volume mounts required
COPY config/clickhouse-config.xml /etc/clickhouse-server/config.d/memory.xml
COPY config/clickhouse-cluster.xml /etc/clickhouse-server/config.d/cluster.xml
COPY config/custom-function.xml /etc/clickhouse-server/custom-function.xml
COPY config/clickhouse-users.xml /etc/clickhouse-server/users.xml
