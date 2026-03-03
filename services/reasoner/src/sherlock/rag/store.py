"""RAGInfra factory — wires all RAG adapters and application services."""
from __future__ import annotations

from dataclasses import dataclass

import structlog
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from sherlock.config import Settings
from sherlock.rag.adapters.embedder import EmbedderAdapter
from sherlock.rag.adapters.minio import MinioFileStore
from sherlock.rag.adapters.pgvector import PgVectorStore
from sherlock.rag.adapters.reranker import RerankerAdapter
from sherlock.rag.application.ingest import IngestPipeline
from sherlock.rag.application.retrieve import HybridRetriever

_log = structlog.get_logger(__name__)


@dataclass
class RAGInfra:
    """Top-level container for all RAG infrastructure components."""

    file_store: MinioFileStore
    vector_store: PgVectorStore
    embedder: EmbedderAdapter
    reranker: RerankerAdapter
    ingest_pipeline: IngestPipeline
    retriever: HybridRetriever
    settings: Settings


async def build_rag_infra(
    settings: Settings,
    engine: AsyncEngine,
    encoder: SentenceTransformer,
) -> RAGInfra:
    """Wire all RAG adapters and application services."""
    file_store = MinioFileStore(settings)
    vector_store = PgVectorStore(engine)
    embedder = EmbedderAdapter(encoder)
    reranker = RerankerAdapter(settings)

    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    ingest = IngestPipeline(
        file_store=file_store,
        vector_store=vector_store,
        embedder=embedder,
        session_factory=session_factory,
        settings=settings,
    )
    retriever = HybridRetriever(
        vector_store=vector_store,
        embedder=embedder,
        reranker=reranker,
    )

    # Verify schema and MinIO connectivity at startup
    await vector_store.init_schema()
    health = await file_store.health_check()
    _log.info("rag.startup", minio_healthy=health.get("minio", False))

    return RAGInfra(
        file_store=file_store,
        vector_store=vector_store,
        embedder=embedder,
        reranker=reranker,
        ingest_pipeline=ingest,
        retriever=retriever,
        settings=settings,
    )
