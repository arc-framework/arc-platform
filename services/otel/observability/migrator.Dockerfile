# ── arc-friday-migrator ───────────────────────────────────────────────────────
# Controlled re-tag of the upstream SigNoz schema migrator under the
# arc-framework registry. No ARC-specific config is baked in — migration
# commands (sync / async) and the ClickHouse DSN are injected at runtime
# via the compose service definitions.
# ─────────────────────────────────────────────────────────────────────────────
FROM signoz/signoz-schema-migrator:v0.142.0

LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL org.opencontainers.image.description="SigNoz schema migrator — ARC-managed re-tag"
LABEL arc.service.name="arc-friday-migrator"
LABEL arc.service.group="arc-friday"
