"""Unit tests for reasoner.memory.SherlockMemory (pgvector backend).

All tests run without live PostgreSQL — every external call is mocked.
asyncio_mode = "auto" is set in pyproject.toml so no explicit @pytest.mark.asyncio
decorator is needed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from reasoner.config import Settings
from reasoner.memory import SherlockMemory


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    """Return a MagicMock Settings with just the attributes SherlockMemory reads."""
    s = MagicMock(spec=Settings)
    s.postgres_url = "postgresql+asyncpg://arc:arc@localhost:5432/arc"
    s.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    s.context_top_k = 5
    s.embedding_dim = 384
    s.sonic_url = "redis://localhost:6379"
    s.context_cache_ttl = 300
    return s


def _make_mock_engine() -> tuple[MagicMock, AsyncMock]:
    """Return (mock_engine, mock_conn) where begin() and connect() work as async ctx managers."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.run_sync = AsyncMock()

    @asynccontextmanager
    async def _begin():  # type: ignore[override]
        yield mock_conn

    @asynccontextmanager
    async def _connect():  # type: ignore[override]
        yield mock_conn

    engine = MagicMock()
    engine.begin = _begin
    engine.connect = _connect
    # event.listens_for accesses engine.sync_engine on SherlockMemory.__init__
    engine.sync_engine = MagicMock()
    return engine, mock_conn


def _make_mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    """Return a session factory whose __call__ returns an async context manager yielding mock_session."""

    @asynccontextmanager
    async def _session_ctx():  # type: ignore[override]
        yield mock_session

    return MagicMock(return_value=_session_ctx())


# ─── init() — PostgreSQL schema bootstrap ─────────────────────────────────────


async def test_init_creates_schema() -> None:
    """init() executes CREATE SCHEMA IF NOT EXISTS reasoner via the async engine."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    executed_stmts = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
    assert any("CREATE SCHEMA IF NOT EXISTS reasoner" in s for s in executed_stmts)


async def test_init_idempotent() -> None:
    """Calling init() twice on the same instance raises no error."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()
        await mem.init()  # must not raise


async def test_init_creates_hnsw_index() -> None:
    """init() executes a CREATE INDEX … USING hnsw statement."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    executed_stmts = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
    assert any("USING hnsw" in s for s in executed_stmts)


async def test_init_calls_create_all() -> None:
    """init() calls conn.run_sync(Base.metadata.create_all) to create the ORM table."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.init()

    mock_conn.run_sync.assert_called_once()


# ─── search() ─────────────────────────────────────────────────────────────────


async def test_search_returns_list_of_strings() -> None:
    """search() returns a list[str] drawn from the database result rows."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = ["past message"]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.search("user1", "test query")

    assert result == ["past message"]


async def test_search_applies_user_id_filter() -> None:
    """search() calls session.execute exactly once with a WHERE clause for the given user_id."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        # Bypass Redis so the pgvector path is always exercised (this test is about SQL filtering)
        mem._redis_failed = True
        await mem.search("alice", "anything")

    # One query is executed per search() call
    mock_session.execute.assert_called_once()
    # Inspect the WHERE clauses of the passed SQLAlchemy Select statement to confirm user_id is filtered
    stmt_arg = mock_session.execute.call_args.args[0]
    where_clauses = stmt_arg.whereclause
    assert where_clauses is not None, "Expected a WHERE clause scoping results to the user"
    # The filter compares Conversation.user_id; verify the bound value is "alice"
    assert str(where_clauses.right.value) == "alice"


# ─── save() ───────────────────────────────────────────────────────────────────


async def test_save_inserts_with_embedding() -> None:
    """save() calls session.add() with a Conversation object that has an embedding."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_encoder = MagicMock()
    fake_vector = [0.1] * 384
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: fake_vector)

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.save("user1", "human", "hello world")

    mock_session.add.assert_called_once()
    conversation_arg = mock_session.add.call_args.args[0]
    assert conversation_arg.user_id == "user1"
    assert conversation_arg.role == "human"
    assert conversation_arg.content == "hello world"
    assert conversation_arg.embedding == fake_vector


async def test_save_commits() -> None:
    """save() calls session.commit() after adding the row."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        await mem.save("user1", "ai", "response")

    mock_session.commit.assert_called_once()


# ─── health_check() ───────────────────────────────────────────────────────────


async def test_health_check_postgres_ok() -> None:
    """When engine.connect() + execute succeeds, health_check returns {"postgres": True}."""
    settings = _make_settings()
    mock_engine, mock_conn = _make_mock_engine()
    mock_conn.execute = AsyncMock()  # succeeds without raising

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.health_check()

    assert result["postgres"] is True


async def test_health_check_postgres_down() -> None:
    """When engine.connect() raises, health_check returns {"postgres": False}."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    @asynccontextmanager
    async def _failing_connect():  # type: ignore[override]
        if True:
            raise ConnectionRefusedError("postgres down")
        yield  # pragma: no cover

    mock_engine.connect = _failing_connect

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.health_check()

    assert result["postgres"] is False


async def test_health_check_no_qdrant_key() -> None:
    """health_check() result must NOT contain a 'qdrant' key."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer"),
        patch("reasoner.memory.sessionmaker"),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        result = await mem.health_check()

    assert "qdrant" not in result


# ─── Redis cache ───────────────────────────────────────────────────────────────


async def test_cache_hit_skips_vector_search() -> None:
    """When Redis has a cached result, session.execute() is NOT called (cache hit)."""
    import json as _json
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    # Inject a mock Redis client that returns a cache hit
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=_json.dumps(["cached context"]))

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        mem._redis = mock_redis  # inject pre-connected mock

        result = await mem.search("user1", "test query")

    assert result == ["cached context"]
    mock_session.execute.assert_not_called()


async def test_cache_invalidated_on_new_message() -> None:
    """After save(), Redis cache keys for the user are deleted (invalidated)."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    deleted_keys: list[str] = []

    async def _scan_iter(pattern: str):
        yield f"arc:ctx:user1:abc123"

    mock_redis = AsyncMock()
    mock_redis.scan_iter = _scan_iter
    mock_redis.delete = AsyncMock(side_effect=lambda k: deleted_keys.append(k))

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        mem._redis = mock_redis

        await mem.save("user1", "human", "new message")

    assert "arc:ctx:user1:abc123" in deleted_keys


async def test_cache_miss_populates_redis() -> None:
    """When Redis misses, the pgvector result is stored in Redis with TTL."""
    import json as _json
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = ["db result"]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # cache miss
    mock_redis.setex = AsyncMock()

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
    ):
        mem = SherlockMemory(settings)
        mem._redis = mock_redis

        result = await mem.search("user1", "query")

    assert result == ["db result"]
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args.args[1] == 300  # TTL = context_cache_ttl
    assert _json.loads(call_args.args[2]) == ["db result"]


async def test_redis_unavailable_falls_through_to_pgvector() -> None:
    """When Redis is unavailable (fail-open), search() still returns pgvector results."""
    settings = _make_settings()
    mock_engine, _ = _make_mock_engine()

    mock_session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = ["pg result"]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with (
        patch("reasoner.memory.create_async_engine", return_value=mock_engine),
        patch("reasoner.memory.SentenceTransformer", return_value=mock_encoder),
        patch("reasoner.memory.sessionmaker", return_value=_make_mock_session_factory(mock_session)),
        patch("reasoner.memory.event"),
        patch("reasoner.memory.aioredis") as mock_aioredis,
    ):
        mock_aioredis.from_url.return_value.ping = AsyncMock(
            side_effect=ConnectionRefusedError("Redis down")
        )
        mem = SherlockMemory(settings)
        result = await mem.search("user1", "query")

    assert result == ["pg result"]
