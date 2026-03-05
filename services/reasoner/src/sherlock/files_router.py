"""OpenAI-compatible Files API router.

Implements POST/GET/DELETE /v1/files and GET /v1/files/{id}/content.
All routes return 503 when RAG is not enabled (state.rag is None).
"""
from __future__ import annotations

import mimetypes
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import metrics
from sqlalchemy import text

from sherlock.rag.adapters.minio import MinioUnavailableError
from sherlock.rag.parsers import UnsupportedFileTypeError

_log = structlog.get_logger(__name__)

_meter = metrics.get_meter("arc-sherlock")
_uploads_counter = _meter.create_counter(
    "sherlock.rag.uploads.total",
    description="Total number of files uploaded via the Files API",
)

_INSERT_FILE_SQL = """\
INSERT INTO sherlock.knowledge_files (id, filename, purpose, bytes, minio_key, status)
VALUES (:id, :filename, :purpose, :bytes, :minio_key, 'uploaded')
"""

_SELECT_ALL_SQL = """\
SELECT id, filename, purpose, bytes, minio_key, status, created_at
FROM sherlock.knowledge_files
ORDER BY created_at DESC
"""

_SELECT_ONE_SQL = """\
SELECT id, filename, purpose, bytes, minio_key, status, created_at
FROM sherlock.knowledge_files
WHERE id = :id
"""

_DELETE_FILE_SQL = """\
DELETE FROM sherlock.knowledge_files WHERE id = :id
"""

_SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".rst", ".py", ".go", ".ts", ".js", ".tsx", ".jsx",
    ".pdf", ".docx", ".json", ".csv",
}


def _file_object(row: Any) -> dict[str, Any]:
    """Serialize a DB row to an OpenAI-compatible file object."""
    return {
        "id": str(row.id),
        "object": "file",
        "filename": row.filename,
        "bytes": row.bytes,
        "created_at": int(row.created_at.timestamp()),
        "purpose": row.purpose,
        "status": row.status,
    }


def build_files_router() -> APIRouter:
    """Return an APIRouter with the OpenAI-compatible Files API.

    Mount with prefix=/v1 in main.py.
    """
    router = APIRouter(tags=["files"])

    @router.post("/files", response_model=None, status_code=201)
    async def upload_file(
        request: Request,
        file: UploadFile,
    ) -> JSONResponse:
        """Upload a file for RAG ingestion (US-1, FR-1)."""
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"error": "Service not ready"}, status_code=503)

        if state.rag is None:
            return JSONResponse({"error": "RAG not enabled"}, status_code=503)

        rag = state.rag

        # Validate extension
        filename = file.filename or ""
        _, ext = os.path.splitext(filename.lower())
        if ext not in _SUPPORTED_EXTENSIONS:
            err = UnsupportedFileTypeError(f"Unsupported file type: {ext!r}")
            return JSONResponse({"error": str(err)}, status_code=400)

        # Read and validate size
        data = await file.read()
        if len(data) > rag.settings.max_file_bytes:
            return JSONResponse(
                {
                    "error": (
                        f"File exceeds maximum allowed size of "
                        f"{rag.settings.max_file_bytes} bytes"
                    )
                },
                status_code=400,
            )

        # Generate file ID and upload to MinIO
        file_id = f"file-{uuid.uuid4()}"
        mime_type = (
            file.content_type
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

        try:
            await rag.file_store.upload(file_id, data, mime_type)
        except MinioUnavailableError as exc:
            _log.error(
                "files.upload.minio_error",
                event_type="exception",
                file_id=file_id,
                error=str(exc),
            )
            return JSONResponse({"error": "Storage unavailable"}, status_code=503)

        # Persist metadata to DB
        async with rag.vector_store._session_factory() as session, session.begin():
            await session.execute(
                text(_INSERT_FILE_SQL),
                {
                    "id": file_id,
                    "filename": filename,
                    "purpose": "assistants",
                    "bytes": len(data),
                    "minio_key": file_id,
                },
            )

        _uploads_counter.add(1, {"ext": ext})
        _log.info(
            "files.uploaded",
            event_type="service_call",
            file_id=file_id,
            filename=filename,
            bytes=len(data),
        )

        # Fetch the inserted row to return accurate created_at
        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_SELECT_ONE_SQL), {"id": file_id})
            row = result.fetchone()

        if row is None:
            return JSONResponse({"error": "Internal error after insert"}, status_code=500)

        return JSONResponse(_file_object(row), status_code=201)

    @router.get("/files", response_model=None)
    async def list_files(request: Request) -> JSONResponse:
        """List all uploaded files (US-6, FR-2)."""
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"error": "Service not ready"}, status_code=503)

        if state.rag is None:
            return JSONResponse({"error": "RAG not enabled"}, status_code=503)

        rag = state.rag

        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_SELECT_ALL_SQL))
            rows = result.fetchall()

        data = [_file_object(row) for row in rows]
        return JSONResponse({"object": "list", "data": data})

    @router.get("/files/{file_id}", response_model=None)
    async def get_file(file_id: str, request: Request) -> JSONResponse:
        """Retrieve file metadata by ID (FR-2)."""
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"error": "Service not ready"}, status_code=503)

        if state.rag is None:
            return JSONResponse({"error": "RAG not enabled"}, status_code=503)

        rag = state.rag

        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_SELECT_ONE_SQL), {"id": file_id})
            row = result.fetchone()

        if row is None:
            return JSONResponse({"error": "File not found"}, status_code=404)

        return JSONResponse(_file_object(row))

    @router.delete("/files/{file_id}", response_model=None)
    async def delete_file(file_id: str, request: Request) -> JSONResponse:
        """Delete a file and its associated chunks (FR-3)."""
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"error": "Service not ready"}, status_code=503)

        if state.rag is None:
            return JSONResponse({"error": "RAG not enabled"}, status_code=503)

        rag = state.rag

        # Verify file exists
        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_SELECT_ONE_SQL), {"id": file_id})
            row = result.fetchone()

        if row is None:
            return JSONResponse({"error": "File not found"}, status_code=404)

        # Delete from DB first (FK cascade removes vector_store_files + knowledge_chunks)
        async with rag.vector_store._session_factory() as session, session.begin():
            await session.execute(text(_DELETE_FILE_SQL), {"id": file_id})

        # Delete from MinIO (best-effort; log on failure, don't fail the request)
        try:
            await rag.file_store.delete(file_id)
        except MinioUnavailableError as exc:
            _log.warning(
                "files.delete.minio_error",
                event_type="exception",
                file_id=file_id,
                error=str(exc),
            )

        _log.info("files.deleted", event_type="service_call", file_id=file_id)

        return JSONResponse({"id": file_id, "object": "file", "deleted": True})

    @router.get("/files/{file_id}/content", response_model=None)
    async def get_file_content(file_id: str, request: Request) -> JSONResponse | StreamingResponse:
        """Stream raw file bytes from MinIO (US-6, FR-2)."""
        try:
            state = request.app.state.app_state
        except AttributeError:
            return JSONResponse({"error": "Service not ready"}, status_code=503)

        if state.rag is None:
            return JSONResponse({"error": "RAG not enabled"}, status_code=503)

        rag = state.rag

        # Verify file exists and retrieve content type
        async with rag.vector_store._session_factory() as session:
            result = await session.execute(text(_SELECT_ONE_SQL), {"id": file_id})
            row = result.fetchone()

        if row is None:
            return JSONResponse({"error": "File not found"}, status_code=404)

        try:
            data = await rag.file_store.download(file_id)
        except MinioUnavailableError as exc:
            _log.error(
                "files.content.minio_error",
                event_type="exception",
                file_id=file_id,
                error=str(exc),
            )
            return JSONResponse({"error": "Storage unavailable"}, status_code=503)

        content_type: str = mimetypes.guess_type(row.filename)[0] or "application/octet-stream"

        async def _stream() -> AsyncGenerator[bytes]:
            yield data

        return StreamingResponse(
            _stream(),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
        )

    return router
