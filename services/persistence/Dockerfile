FROM postgres:17-alpine

LABEL org.opencontainers.image.title="ARC Oracle — Persistence"
LABEL org.opencontainers.image.description="PostgreSQL 17 persistence layer for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-oracle"
LABEL arc.service.codename="oracle"
LABEL arc.service.tech="postgres"

# postgres user (uid 70) is the default in postgres:17-alpine — no USER directive needed.
# The postgres image already drops privileges to uid 70 on container start.
