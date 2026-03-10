---
url: /arc-platform/docs/services/vector-db.md
---
# Vector Database

> **Status:** Planned | **Profile:** TBD

A dedicated vector retrieval service is planned for a future release.

## Current State

Vector storage is currently handled by PostgreSQL 17 + pgvector inside the `persistence` service (Oracle). See [SQL Database (Oracle)](./sql-db.md) for details on the current implementation.

## Planned Role

The `arc-db-vector` service will offload all embedding storage and approximate nearest-neighbour search from the relational database, enabling independent scaling of vector workloads.

No Make targets or ports are assigned yet — this page will be updated when the service is active.
