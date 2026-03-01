import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sherlock.config import Settings

_log = logging.getLogger(__name__)


# ─── ORM Model ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "sherlock"}

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(index=True)
    role: Mapped[str]       # "human" | "ai"
    content: Mapped[str]
    created_at: Mapped[Optional[datetime]] = mapped_column(
        server_default=text("now()"), nullable=True
    )


# ─── SherlockMemory ───────────────────────────────────────────────────────────

class SherlockMemory:
    """Dual-store memory: Qdrant (semantic search) + PostgreSQL (ordered history)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._qdrant: AsyncQdrantClient = AsyncQdrantClient(
            host=settings.qdrant_host, port=settings.qdrant_port
        )
        self._engine: AsyncEngine = create_async_engine(settings.postgres_url)
        self._session_factory: Any = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._encoder: SentenceTransformer = SentenceTransformer(
            settings.embedding_model
        )
        self._top_k: int = settings.context_top_k
        self._collection: str = settings.qdrant_collection
        self._dim: int = settings.embedding_dim

    async def init(self) -> None:
        """Create Qdrant collection and PostgreSQL schema+table if absent.

        Best-effort: logs a warning and returns if deps are unreachable.
        The service starts in degraded mode; /health/deep reports the status.
        """
        try:
            collections = await self._qdrant.get_collections()
            existing = {c.name for c in collections.collections}
            if self._collection not in existing:
                await self._qdrant.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
                )
        except Exception as exc:
            _log.warning("qdrant_unavailable_at_init", error=str(exc))

        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS sherlock"))
                await conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS sherlock.conversations (
                            id          TEXT PRIMARY KEY,
                            user_id     TEXT NOT NULL,
                            role        TEXT NOT NULL,
                            content     TEXT NOT NULL,
                            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    )
                )
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id "
                        "ON sherlock.conversations (user_id)"
                    )
                )
        except Exception as exc:
            _log.warning("postgres_unavailable_at_init", error=str(exc))

    async def search(self, user_id: str, text_query: str) -> list[str]:
        """Encode query and search Qdrant with user_id filter; return top-k strings."""
        vector: list[float] = self._encoder.encode(text_query).tolist()
        results = await self._qdrant.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=self._top_k,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id),
                    )
                ]
            ),
        )
        return [hit.payload["content"] for hit in results if hit.payload]

    async def save(self, user_id: str, role: str, content: str) -> None:
        """Persist a conversation turn to both Qdrant (vector) and PostgreSQL (row)."""
        vector: list[float] = self._encoder.encode(content).tolist()
        point_id = str(uuid.uuid4())

        # Qdrant upsert
        await self._qdrant.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"user_id": user_id, "role": role, "content": content},
                )
            ],
        )

        # PostgreSQL insert
        async with self._session_factory() as session:
            session.add(
                Conversation(
                    id=point_id,
                    user_id=user_id,
                    role=role,
                    content=content,
                )
            )
            await session.commit()

    async def health_check(self) -> dict[str, bool]:
        """Probe Qdrant and PostgreSQL independently; one failure does not mask the other."""
        qdrant_ok = False
        postgres_ok = False

        try:
            await self._qdrant.get_collections()
            qdrant_ok = True
        except Exception:
            pass

        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            postgres_ok = True
        except Exception:
            pass

        return {"qdrant": qdrant_ok, "postgres": postgres_ok}
