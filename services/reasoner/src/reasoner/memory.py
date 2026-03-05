import asyncio
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

import redis.asyncio as aioredis
import structlog
from pgvector.asyncpg import register_vector
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from reasoner.config import Settings

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
    __table_args__ = {"schema": "reasoner"}

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(index=True)
    role: Mapped[str]       # "human" | "ai"
    content: Mapped[str]
    embedding: Mapped[list] = mapped_column(Vector(384), nullable=True)  # type: ignore[type-arg]
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
        self._session_factory: Any = sessionmaker(  # type: ignore[call-overload]
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._encoder: SentenceTransformer = SentenceTransformer(
            settings.embedding_model
        )
        self._top_k: int = settings.context_top_k
        self._dim: int = settings.embedding_dim
        # Dedicated executor so CPU-bound encoding never blocks the event loop
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2)

        # Redis (Sonic) — lazy-connect, fail-open
        self._sonic_url: str = settings.sonic_url
        self._cache_ttl: int = settings.context_cache_ttl
        self._redis: aioredis.Redis | None = None  # type: ignore[type-arg]
        self._redis_failed: bool = False

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
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS reasoner"))
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_conversations_embedding "
                        "ON reasoner.conversations "
                        "USING hnsw (embedding vector_cosine_ops)"
                    )
                )
        except Exception as exc:
            _log.warning("postgres_unavailable_at_init", error=str(exc))

    async def _get_redis(self) -> "aioredis.Redis | None":  # type: ignore[type-arg]
        """Return cached Redis client, or None if unavailable (fail-open)."""
        if self._redis is not None:
            return self._redis
        if self._redis_failed:
            return None
        try:
            r: aioredis.Redis = aioredis.from_url(self._sonic_url, decode_responses=True)  # type: ignore[type-arg]
            await r.ping()
            self._redis = r
            return self._redis
        except Exception as exc:
            _log.warning("redis_unavailable", error=str(exc))
            self._redis_failed = True
            return None

    async def search(self, user_id: str, text_query: str) -> list[str]:
        """Encode query and search pgvector with user_id filter; return top-k strings.

        Checks Redis cache first (key: arc:ctx:{user_id}:{sha256(embedding)}).
        Cache miss falls through to pgvector; result is stored in Redis for TTL seconds.
        Redis unavailable → fail-open, query pgvector directly.
        """
        loop = asyncio.get_event_loop()
        vector: list[float] = await loop.run_in_executor(
            self._executor, lambda: self._encoder.encode(text_query).tolist()
        )

        emb_hash = hashlib.sha256(
            json.dumps(vector, separators=(",", ":")).encode()
        ).hexdigest()
        cache_key = f"arc:ctx:{user_id}:{emb_hash}"

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                cached = await redis_client.get(cache_key)
                if cached is not None:
                    return json.loads(cached)
            except Exception as exc:
                _log.warning("redis_get_failed", error=str(exc))

        async with self._session_factory() as session:
            result = await session.execute(
                select(Conversation.content)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.embedding.cosine_distance(vector))
                .limit(self._top_k)
            )
            rows: list[str] = list(result.scalars().all())

        if redis_client is not None:
            try:
                await redis_client.setex(cache_key, self._cache_ttl, json.dumps(rows))
            except Exception as exc:
                _log.warning("redis_set_failed", error=str(exc))

        return rows

    async def save(self, user_id: str, role: str, content: str) -> None:
        """Persist a conversation turn to PostgreSQL with vector embedding.

        After commit, invalidates all Redis cache keys for this user so subsequent
        searches reflect the newly-saved context (fail-open: Redis unavailable is ignored).
        """
        loop = asyncio.get_event_loop()
        vector: list[float] = await loop.run_in_executor(
            self._executor, lambda: self._encoder.encode(content).tolist()
        )
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

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                async for key in redis_client.scan_iter(f"arc:ctx:{user_id}:*"):
                    await redis_client.delete(key)
            except Exception as exc:
                _log.warning("redis_invalidate_failed", error=str(exc))

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
