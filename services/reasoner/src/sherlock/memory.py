import uuid
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

import structlog
from pgvector.asyncpg import register_vector
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sherlock.config import Settings

_log = structlog.get_logger(__name__)


# ─── MemoryBackend Protocol ───────────────────────────────────────────────────

@runtime_checkable
class MemoryBackend(Protocol):
    async def search(self, user_id: str, query: str) -> list[str]: ...
    async def save(self, user_id: str, role: str, content: str) -> None: ...
    async def health_check(self) -> dict[str, bool]: ...


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
    embedding: Mapped[list] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        server_default=text("now()"), nullable=True
    )


# ─── SherlockMemory ───────────────────────────────────────────────────────────

class SherlockMemory:
    """Single-store memory: PostgreSQL + pgvector for semantic search and ordered history.

    Implements: MemoryBackend
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(settings.postgres_url)
        self._session_factory: Any = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._encoder: SentenceTransformer = SentenceTransformer(
            settings.embedding_model
        )
        self._top_k: int = settings.context_top_k
        self._dim: int = settings.embedding_dim

        # asyncpg requires the vector codec registered per connection
        @event.listens_for(self._engine.sync_engine, "connect")
        def _on_connect(dbapi_conn: Any, _: Any) -> None:
            dbapi_conn.run_async(register_vector)

    async def init(self) -> None:
        """Create PostgreSQL schema, table, and HNSW vector index if absent.

        Best-effort: logs a warning and returns if the database is unreachable.
        The service starts in degraded mode; /health/deep reports the status.
        """
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS sherlock"))
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_embedding "
                        "ON sherlock.conversations "
                        "USING hnsw (embedding vector_cosine_ops)"
                    )
                )
        except Exception as exc:
            _log.warning("postgres_unavailable_at_init", error=str(exc))

    async def search(self, user_id: str, text_query: str) -> list[str]:
        """Encode query and search pgvector with user_id filter; return top-k strings."""
        vector: list[float] = self._encoder.encode(text_query).tolist()
        async with self._session_factory() as session:
            result = await session.execute(
                select(Conversation.content)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.embedding.cosine_distance(vector))
                .limit(self._top_k)
            )
            return list(result.scalars().all())

    async def save(self, user_id: str, role: str, content: str) -> None:
        """Persist a conversation turn to PostgreSQL with vector embedding."""
        vector: list[float] = self._encoder.encode(content).tolist()
        async with self._session_factory() as session:
            session.add(
                Conversation(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    role=role,
                    content=content,
                    embedding=vector,
                )
            )
            await session.commit()

    async def health_check(self) -> dict[str, bool]:
        """Probe PostgreSQL; returns {"postgres": bool}."""
        postgres_ok = False
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            postgres_ok = True
        except Exception:
            pass
        return {"postgres": postgres_ok}
