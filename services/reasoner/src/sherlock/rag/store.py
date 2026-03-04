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
) -> RAGInfra | None:
    """Wire all RAG adapters and application services.

    Returns None (and logs a warning) when MinIO is unreachable at startup so
    the service can continue in degraded mode — all RAG routes will return 503
    until the storage dependency becomes healthy and the service is restarted.
    """
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

    await vector_store.init_schema()

    health = await file_store.health_check()
    minio_ok = health.get("minio", False)
    if not minio_ok:
        _log.warning(
            "rag.startup.degraded",
            reason="MinIO (arc-storage) unreachable",
            endpoint=settings.minio_endpoint,
            hint="Start arc-storage with 'make dev PROFILE=reason' or set SHERLOCK_RAG_ENABLED=false",
        )
        return None

    _log.info("rag.startup.ok", bucket=settings.minio_bucket)
    return RAGInfra(
        file_store=file_store,
        vector_store=vector_store,
        embedder=embedder,
        reranker=reranker,
        ingest_pipeline=ingest,
        retriever=retriever,
        settings=settings,
    )
