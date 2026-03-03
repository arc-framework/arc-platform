"""RAG domain entities.

Plain Pydantic models — no ORM attachment. Adapters handle DB operations.
DB schema: services/persistence/initdb/004_sherlock_rag_schema.sql
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── VectorStore ──────────────────────────────────────────────────────────────


class VectorStore(BaseModel):
    """A named collection of indexed knowledge files."""

    id: str = Field(default_factory=lambda: f"vs-{uuid.uuid4()}")
    name: str
    file_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── KnowledgeFile ────────────────────────────────────────────────────────────

KnowledgeFileStatus = Literal["uploaded", "processing", "completed", "failed"]


class KnowledgeFile(BaseModel):
    """An uploaded file stored in MinIO, pending or completed ingestion."""

    id: str = Field(default_factory=lambda: f"file-{uuid.uuid4()}")
    filename: str
    purpose: str = "assistants"
    bytes: int = 0
    minio_key: str
    status: KnowledgeFileStatus = "uploaded"
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── VectorStoreFile ──────────────────────────────────────────────────────────

VectorStoreFileStatus = Literal["pending", "processing", "completed", "failed"]


class VectorStoreFile(BaseModel):
    """Join row linking a KnowledgeFile to a VectorStore, with ingest status."""

    vector_store_id: str
    file_id: str
    status: VectorStoreFileStatus = "pending"
    chunk_count: int | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── KnowledgeChunk ───────────────────────────────────────────────────────────


class KnowledgeChunk(BaseModel):
    """A text chunk with its dense embedding, derived from a KnowledgeFile.

    ``embedding`` is 384-dimensional (all-MiniLM-L6-v2 default).
    ``fts_vector`` is DB-generated (GENERATED ALWAYS) and not represented here.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vector_store_id: str
    file_id: str
    chunk_index: int
    content: str
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── SearchResult ─────────────────────────────────────────────────────────────


class SearchResult(BaseModel):
    """A single result from hybrid (dense + FTS) vector search."""

    chunk_id: str
    vector_store_id: str
    file_id: str
    content: str
    score: float
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── IngestJob ────────────────────────────────────────────────────────────────


class IngestJob(BaseModel):
    """Value object describing a pending file-to-vector-store ingest operation."""

    file_id: str
    vector_store_id: str


# ─── ParsedDocument ───────────────────────────────────────────────────────────


class ParsedDocument(BaseModel):
    """Output of a file parser: raw extracted text plus source metadata."""

    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
