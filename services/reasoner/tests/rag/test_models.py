"""Unit tests for reasoner.rag.domain.models."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from reasoner.rag.domain.models import (
    IngestJob,
    KnowledgeChunk,
    KnowledgeFile,
    ParsedDocument,
    SearchResult,
    VectorStore,
    VectorStoreFile,
)


# ─── VectorStore ──────────────────────────────────────────────────────────────


class TestVectorStore:
    def test_default_id_has_vs_prefix(self) -> None:
        vs = VectorStore(name="test")
        assert vs.id.startswith("vs-")

    def test_default_file_count_is_zero(self) -> None:
        vs = VectorStore(name="my-store")
        assert vs.file_count == 0

    def test_custom_values_are_preserved(self) -> None:
        vs = VectorStore(name="store", file_count=7, metadata={"owner": "alice"})
        assert vs.name == "store"
        assert vs.file_count == 7
        assert vs.metadata == {"owner": "alice"}

    def test_created_at_is_utc(self) -> None:
        vs = VectorStore(name="store")
        assert vs.created_at.tzinfo is not None

    @pytest.mark.parametrize("name", ["alpha", "beta", "gamma-store"])
    def test_various_names(self, name: str) -> None:
        vs = VectorStore(name=name)
        assert vs.name == name

    def test_unique_ids_per_instance(self) -> None:
        a = VectorStore(name="a")
        b = VectorStore(name="b")
        assert a.id != b.id


# ─── KnowledgeFile ────────────────────────────────────────────────────────────


class TestKnowledgeFile:
    def test_default_id_has_file_prefix(self) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="key/doc.txt")
        assert f.id.startswith("file-")

    def test_default_status_is_uploaded(self) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="key/doc.txt")
        assert f.status == "uploaded"

    def test_default_purpose_is_assistants(self) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="key/doc.txt")
        assert f.purpose == "assistants"

    @pytest.mark.parametrize(
        "status",
        ["uploaded", "processing", "completed", "failed"],
    )
    def test_valid_status_values(self, status: str) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="k", status=status)  # type: ignore[arg-type]
        assert f.status == status

    def test_bytes_default_is_zero(self) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="k")
        assert f.bytes == 0

    def test_created_at_is_timezone_aware(self) -> None:
        f = KnowledgeFile(filename="doc.txt", minio_key="k")
        assert f.created_at.tzinfo is not None


# ─── VectorStoreFile ──────────────────────────────────────────────────────────


class TestVectorStoreFile:
    def test_default_status_is_queued(self) -> None:
        vsf = VectorStoreFile(vector_store_id="vs-1", file_id="file-1")
        assert vsf.status == "queued"

    def test_optional_fields_default_to_none(self) -> None:
        vsf = VectorStoreFile(vector_store_id="vs-1", file_id="file-1")
        assert vsf.chunk_count is None
        assert vsf.error_message is None

    @pytest.mark.parametrize(
        "status",
        ["queued", "pending", "processing", "completed", "failed"],
    )
    def test_valid_status_values(self, status: str) -> None:
        vsf = VectorStoreFile(vector_store_id="v", file_id="f", status=status)  # type: ignore[arg-type]
        assert vsf.status == status

    def test_chunk_count_and_error_settable(self) -> None:
        vsf = VectorStoreFile(
            vector_store_id="v",
            file_id="f",
            status="failed",
            chunk_count=0,
            error_message="parse error",
        )
        assert vsf.chunk_count == 0
        assert vsf.error_message == "parse error"


# ─── KnowledgeChunk ───────────────────────────────────────────────────────────


class TestKnowledgeChunk:
    def test_id_is_uuid_string(self) -> None:
        chunk = KnowledgeChunk(
            vector_store_id="vs-1",
            file_id="file-1",
            chunk_index=0,
            content="hello world",
        )
        # Should be parseable as UUID
        uuid.UUID(chunk.id)

    def test_embedding_defaults_to_empty_list(self) -> None:
        chunk = KnowledgeChunk(
            vector_store_id="vs-1",
            file_id="file-1",
            chunk_index=0,
            content="text",
        )
        assert chunk.embedding == []

    def test_embedding_stored_correctly(self) -> None:
        emb = [0.1, 0.2, 0.3]
        chunk = KnowledgeChunk(
            vector_store_id="vs-1",
            file_id="file-1",
            chunk_index=2,
            content="text",
            embedding=emb,
        )
        assert chunk.embedding == emb

    def test_created_at_is_utc(self) -> None:
        chunk = KnowledgeChunk(
            vector_store_id="vs-1", file_id="f", chunk_index=0, content="t"
        )
        assert chunk.created_at.tzinfo is not None


# ─── SearchResult ─────────────────────────────────────────────────────────────


class TestSearchResult:
    def test_basic_fields(self) -> None:
        sr = SearchResult(
            chunk_id="c-1",
            vector_store_id="vs-1",
            file_id="f-1",
            content="relevant content",
            score=0.87,
            chunk_index=3,
        )
        assert sr.chunk_id == "c-1"
        assert sr.vector_store_id == "vs-1"
        assert sr.file_id == "f-1"
        assert sr.score == pytest.approx(0.87)
        assert sr.chunk_index == 3
        assert sr.content == "relevant content"

    def test_metadata_defaults_to_empty_dict(self) -> None:
        sr = SearchResult(
            chunk_id="c", vector_store_id="vs", file_id="f", content="x", score=0.5, chunk_index=0
        )
        assert sr.metadata == {}

    def test_metadata_stored(self) -> None:
        sr = SearchResult(
            chunk_id="c",
            vector_store_id="vs",
            file_id="f",
            content="x",
            score=0.5,
            chunk_index=0,
            metadata={"source": "wiki"},
        )
        assert sr.metadata == {"source": "wiki"}


# ─── IngestJob ────────────────────────────────────────────────────────────────


class TestIngestJob:
    def test_fields_set_correctly(self) -> None:
        job = IngestJob(file_id="file-abc", vector_store_id="vs-xyz")
        assert job.file_id == "file-abc"
        assert job.vector_store_id == "vs-xyz"

    @pytest.mark.parametrize(
        "file_id,vs_id",
        [
            ("file-1", "vs-1"),
            ("file-2", "vs-2"),
            ("file-999", "vs-000"),
        ],
    )
    def test_parametrized_ingest_jobs(self, file_id: str, vs_id: str) -> None:
        job = IngestJob(file_id=file_id, vector_store_id=vs_id)
        assert job.file_id == file_id
        assert job.vector_store_id == vs_id


# ─── ParsedDocument ───────────────────────────────────────────────────────────


class TestParsedDocument:
    def test_text_required(self) -> None:
        doc = ParsedDocument(text="hello")
        assert doc.text == "hello"

    def test_metadata_defaults_to_empty_dict(self) -> None:
        doc = ParsedDocument(text="x")
        assert doc.metadata == {}

    def test_metadata_preserved(self) -> None:
        doc = ParsedDocument(text="x", metadata={"type": "pdf", "pages": 3})
        assert doc.metadata["type"] == "pdf"
        assert doc.metadata["pages"] == 3

    def test_empty_text_allowed(self) -> None:
        doc = ParsedDocument(text="")
        assert doc.text == ""


# ─── Cross-model timestamp consistency ────────────────────────────────────────


class TestTimestampConsistency:
    def test_all_models_created_at_are_utc(self) -> None:
        now = datetime.now(UTC)
        vs = VectorStore(name="t")
        kf = KnowledgeFile(filename="f", minio_key="k")
        chunk = KnowledgeChunk(vector_store_id="v", file_id="f", chunk_index=0, content="c")

        for model in [vs, kf, chunk]:
            assert model.created_at.tzinfo is not None
            assert model.created_at >= now or abs((model.created_at - now).total_seconds()) < 1
