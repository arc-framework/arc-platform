"""OpenAI-compatible Vector Stores API router.

Endpoints (all mounted under /v1):
  POST   /vector_stores                    → 201
  GET    /vector_stores/{id}               → 200 / 404
  DELETE /vector_stores/{id}               → 200 / 404
  POST   /vector_stores/{id}/files         → 202 async / 200 sync (?sync=true)
  GET    /vector_stores/{id}/files/{fid}   → 200 / 404
  DELETE /vector_stores/{id}/files/{fid}   → 200 / 404
  POST   /vector_stores/{id}/search        → 200

All routes return 503 when state.rag is None.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from opentelemetry import metrics
from pydantic import BaseModel, Field
from sqlalchemy import text

_log = structlog.get_logger(__name__)

_meter = metrics.get_meter("arc-reasoner")
_ingest_latency = _meter.create_histogram(
    "reasoner.rag.ingest.latency",
    description="RAG ingest latency in milliseconds",
    unit="ms",
)
_search_latency = _meter.create_histogram(
    "reasoner.rag.search.latency",
    description="RAG search latency in milliseconds",
    unit="ms",
)


# ─── Request / Response models ────────────────────────────────────────────────


class CreateVectorStoreRequest(BaseModel):
    name: str


class AttachFileRequest(BaseModel):
    file_id: str


class SearchRequest(BaseModel):
    query: str
    hybrid_alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=1)


# ─── SQL helpers ──────────────────────────────────────────────────────────────

_VS_INSERT = """
INSERT INTO reasoner.vector_stores (id, name)
VALUES (:id, :name)
"""

_VS_SELECT = "SELECT id, name, created_at FROM reasoner.vector_stores WHERE id = :id"

_VS_DELETE = "DELETE FROM reasoner.vector_stores WHERE id = :id RETURNING id"

_VSF_INSERT = """
INSERT INTO reasoner.vector_store_files (vector_store_id, file_id, status)
VALUES (:vs_id, :file_id, 'queued')
ON CONFLICT (vector_store_id, file_id) DO NOTHING
"""

_VSF_SELECT = """
SELECT vector_store_id, file_id, status, chunk_count, error_message
FROM reasoner.vector_store_files
WHERE vector_store_id = :vs_id AND file_id = :fid
"""

_VSF_DELETE = """
DELETE FROM reasoner.vector_store_files
WHERE vector_store_id = :vs_id AND file_id = :fid
RETURNING file_id
"""


# ─── Router factory ───────────────────────────────────────────────────────────


def build_vector_stores_router() -> APIRouter:
    """Return an APIRouter with all /vector_stores routes.

    Mount with prefix=/v1 in main.py.
    """
    router = APIRouter(tags=["vector_stores"])

    # ── Guard helpers ─────────────────────────────────────────────────────────

    def _rag(request: Request) -> Any:
        """Return state.rag or raise 503-signalling sentinel."""
        try:
            rag = request.app.state.app_state.rag
        except AttributeError:
            rag = None
        return rag

    def _503() -> JSONResponse:
        return JSONResponse({"detail": "RAG infrastructure not available"}, status_code=503)

    # ── POST /vector_stores ───────────────────────────────────────────────────

    @router.post("/vector_stores", response_model=None)
    async def create_vector_store(
        body: CreateVectorStoreRequest,
        request: Request,
    ) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        vs_id = f"vs-{uuid.uuid4()}"
        async with rag.vector_store._session_factory() as session, session.begin():
            await session.execute(
                text(_VS_INSERT),
                {"id": vs_id, "name": body.name},
            )

        _log.info("vector_store.created", vs_id=vs_id, name=body.name)
        return JSONResponse(
            {
                "id": vs_id,
                "object": "vector_store",
                "name": body.name,
                "created_at": int(time.time()),
            },
            status_code=201,
        )

    # ── GET /vector_stores/{vs_id} ────────────────────────────────────────────

    @router.get("/vector_stores/{vs_id}", response_model=None)
    async def get_vector_store(vs_id: str, request: Request) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_VS_SELECT), {"id": vs_id})
            row = result.fetchone()

        if row is None:
            return JSONResponse({"detail": "Vector store not found"}, status_code=404)

        return JSONResponse({
            "id": str(row.id),
            "object": "vector_store",
            "name": row.name,
            "created_at": int(row.created_at.timestamp()),
        })

    # ── DELETE /vector_stores/{vs_id} ─────────────────────────────────────────

    @router.delete("/vector_stores/{vs_id}", response_model=None)
    async def delete_vector_store(vs_id: str, request: Request) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        async with rag.vector_store._session_factory() as session, session.begin():
            result = await session.execute(text(_VS_DELETE), {"id": vs_id})
            deleted = result.fetchone()

        if deleted is None:
            return JSONResponse({"detail": "Vector store not found"}, status_code=404)

        _log.info("vector_store.deleted", vs_id=vs_id)
        return JSONResponse({"id": vs_id, "object": "vector_store", "deleted": True})

    # ── POST /vector_stores/{vs_id}/files ─────────────────────────────────────

    @router.post("/vector_stores/{vs_id}/files", response_model=None)
    async def attach_file(
        vs_id: str,
        body: AttachFileRequest,
        request: Request,
        background_tasks: BackgroundTasks,
        sync: bool = False,
    ) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        file_id = body.file_id

        # Idempotent insert — ON CONFLICT DO NOTHING
        async with rag.vector_store._session_factory() as session, session.begin():
            await session.execute(
                text(_VSF_INSERT),
                {"vs_id": vs_id, "file_id": file_id},
            )

        # Check whether the row already existed (status != queued means already ingested)
        async with rag.vector_store._session_factory() as session:
            result = await session.execute(
                text(_VSF_SELECT),
                {"vs_id": vs_id, "fid": file_id},
            )
            row = result.fetchone()

        if row is not None and row.status not in ("queued", "pending"):
            # Return existing state — idempotent response
            return JSONResponse(
                {
                    "id": file_id,
                    "object": "vector_store.file",
                    "status": row.status,
                    "chunk_count": row.chunk_count,
                    "error": row.error_message,
                },
                status_code=200,
            )

        if sync:
            start = time.monotonic()
            try:
                chunks = await asyncio.wait_for(
                    rag.ingest_pipeline.ingest(file_id, vs_id),
                    timeout=rag.settings.sync_timeout_s,
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                _ingest_latency.record(latency_ms, {"sync": "true"})
                _log.info(
                    "rag.ingest.sync.completed",
                    vs_id=vs_id,
                    file_id=file_id,
                    chunks=chunks,
                    latency_ms=latency_ms,
                )
                return JSONResponse(
                    {
                        "id": file_id,
                        "object": "vector_store.file",
                        "status": "completed",
                        "chunk_count": chunks,
                        "error": None,
                    },
                    status_code=200,
                )
            except TimeoutError:
                # Timeout — fall back to async
                asyncio.create_task(rag.ingest_pipeline.ingest(file_id, vs_id))
                _log.warning(
                    "rag.ingest.sync.timeout_fallback",
                    vs_id=vs_id,
                    file_id=file_id,
                    timeout_s=rag.settings.sync_timeout_s,
                )
                return JSONResponse(
                    {
                        "id": file_id,
                        "object": "vector_store.file",
                        "status": "queued",
                        "chunk_count": None,
                        "error": None,
                    },
                    status_code=202,
                )

        # Async path — fire-and-forget background task
        background_tasks.add_task(rag.ingest_pipeline.ingest, file_id, vs_id)
        _log.info("rag.ingest.queued", vs_id=vs_id, file_id=file_id)
        return JSONResponse(
            {
                "id": file_id,
                "object": "vector_store.file",
                "status": "queued",
                "chunk_count": None,
                "error": None,
            },
            status_code=202,
        )

    # ── GET /vector_stores/{vs_id}/files/{fid} ────────────────────────────────

    @router.get("/vector_stores/{vs_id}/files/{fid}", response_model=None)
    async def get_file_status(vs_id: str, fid: str, request: Request) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        async with rag.vector_store._session_factory() as session:
            result = await session.execute(
                text(_VSF_SELECT),
                {"vs_id": vs_id, "fid": fid},
            )
            row = result.fetchone()

        if row is None:
            return JSONResponse({"detail": "File not found in vector store"}, status_code=404)

        return JSONResponse({
            "id": fid,
            "object": "vector_store.file",
            "status": row.status,
            "chunk_count": row.chunk_count,
            "error": row.error_message,
        })

    # ── DELETE /vector_stores/{vs_id}/files/{fid} ─────────────────────────────

    @router.delete("/vector_stores/{vs_id}/files/{fid}", response_model=None)
    async def delete_file(vs_id: str, fid: str, request: Request) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        async with rag.vector_store._session_factory() as session, session.begin():
            result = await session.execute(
                text(_VSF_DELETE),
                {"vs_id": vs_id, "fid": fid},
            )
            deleted = result.fetchone()

        if deleted is None:
            return JSONResponse({"detail": "File not found in vector store"}, status_code=404)

        # Remove chunks from knowledge_chunks (cascade backup for manual cleanup)
        await rag.vector_store.delete_by_file(fid)

        _log.info("vector_store_file.deleted", vs_id=vs_id, file_id=fid)
        return JSONResponse({"id": fid, "object": "vector_store.file", "deleted": True})

    # ── POST /vector_stores/{vs_id}/search ────────────────────────────────────

    @router.post("/vector_stores/{vs_id}/search", response_model=None)
    async def search(
        vs_id: str,
        body: SearchRequest,
        request: Request,
    ) -> JSONResponse:
        rag = _rag(request)
        if rag is None:
            return _503()

        alpha = body.hybrid_alpha if body.hybrid_alpha is not None else rag.settings.hybrid_alpha
        top_k = body.top_k if body.top_k is not None else rag.settings.retrieval_top_k
        candidate_k = rag.settings.retrieval_candidate_k

        start = time.monotonic()
        results = await rag.retriever.search(
            query=body.query,
            vs_ids=[vs_id],
            alpha=alpha,
            candidate_k=candidate_k,
            top_k=top_k,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        _search_latency.record(latency_ms, {"vs_id": vs_id})

        _log.debug(
            "rag.search.completed",
            vs_id=vs_id,
            query_len=len(body.query),
            result_count=len(results),
            latency_ms=latency_ms,
        )

        return JSONResponse({
            "object": "list",
            "data": [
                {
                    "chunk_id": r.chunk_id,
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        })

    return router
