FROM openbao/openbao

LABEL org.opencontainers.image.title="ARC Nick Fury — Secrets"
LABEL org.opencontainers.image.description="OpenBao secrets management for the A.R.C. Platform"
LABEL org.opencontainers.image.source="https://github.com/arc-framework/arc-platform"
LABEL arc.service.name="arc-vault"
LABEL arc.service.codename="nick-fury"
LABEL arc.service.tech="openbao"

# openbao/openbao runs as root by default. Nick Fury uses -dev mode: in-memory, auto-unsealed, known root token. Root is acceptable for this DEVELOPMENT-ONLY service. For production: Raft-backed storage + TLS + non-root user.
