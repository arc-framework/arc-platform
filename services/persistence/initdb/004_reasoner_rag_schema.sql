-- 004_reasoner_rag_schema.sql
-- RAG knowledge base tables for the reasoner service (feature 013).
-- Requires: 003_enable_pgvector.sql (CREATE EXTENSION vector already applied).
-- All tables use IF NOT EXISTS — safe on re-run and on 012 cold start.

CREATE SCHEMA IF NOT EXISTS reasoner;

CREATE TABLE IF NOT EXISTS reasoner.vector_stores (
    id          text PRIMARY KEY DEFAULT 'vs-' || gen_random_uuid()::text,
    name        text NOT NULL,
    file_count  integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reasoner.knowledge_files (
    id          text PRIMARY KEY DEFAULT 'file-' || gen_random_uuid()::text,
    filename    text NOT NULL,
    purpose     text NOT NULL DEFAULT 'assistants',
    bytes       bigint NOT NULL DEFAULT 0,
    minio_key   text NOT NULL,
    status      text NOT NULL DEFAULT 'uploaded',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reasoner.vector_store_files (
    vector_store_id text NOT NULL REFERENCES reasoner.vector_stores(id) ON DELETE CASCADE,
    file_id         text NOT NULL REFERENCES reasoner.knowledge_files(id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'queued',
    chunk_count     integer,
    error_message   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (vector_store_id, file_id)
);

CREATE TABLE IF NOT EXISTS reasoner.knowledge_chunks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vector_store_id text NOT NULL REFERENCES reasoner.vector_stores(id) ON DELETE CASCADE,
    file_id         text NOT NULL REFERENCES reasoner.knowledge_files(id) ON DELETE CASCADE,
    chunk_index     integer NOT NULL,
    content         text NOT NULL,
    embedding       vector(384),
    fts_vector      tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_vs_id
    ON reasoner.knowledge_chunks (vector_store_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
    ON reasoner.knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
    ON reasoner.knowledge_chunks USING gin (fts_vector);
