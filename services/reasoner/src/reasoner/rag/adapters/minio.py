"""MinIO file store adapter.

Implements ``FileStorePort`` using the MinIO Python SDK (synchronous C extension).
Every SDK call is wrapped in ``asyncio.to_thread()`` to avoid blocking FastAPI's
event loop.
"""

from __future__ import annotations

import asyncio
import io

import structlog
import urllib3
from minio import Minio
from minio.error import S3Error

from reasoner.config import Settings

_log = structlog.get_logger(__name__)


class MinioUnavailableError(Exception):
    """Raised when MinIO cannot be reached or a bucket operation fails."""


class MinioFileStore:
    """FileStorePort implementation backed by MinIO S3-compatible storage."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.minio_bucket
        # Short connect timeout + no urllib3 retries so health checks fail fast
        # when arc-storage is not in the active profile (e.g. think profile).
        _http = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=10.0),
            retries=urllib3.Retry(total=0),
        )
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key.get_secret_value(),
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=settings.minio_secure,
            http_client=_http,
        )

    # ─── Bucket helpers (sync — called inside to_thread) ──────────────────────

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    # ─── FileStorePort interface ───────────────────────────────────────────────

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        """Store *data* at *key*, creating the bucket if it does not exist."""

        def _sync() -> None:
            self._ensure_bucket()
            self._client.put_object(
                self._bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        try:
            await asyncio.to_thread(_sync)
        except S3Error as exc:
            raise MinioUnavailableError(
                f"MinIO upload failed for key={key!r}: {exc}"
            ) from exc
        except Exception as exc:
            raise MinioUnavailableError(
                f"MinIO unreachable during upload (key={key!r}): {exc}"
            ) from exc

        _log.debug("minio.upload", key=key, bytes=len(data))

    async def download(self, key: str) -> bytes:
        """Retrieve the object at *key* and return its raw bytes."""

        def _sync() -> bytes:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()

        try:
            data: bytes = await asyncio.to_thread(_sync)
        except S3Error as exc:
            raise MinioUnavailableError(
                f"MinIO download failed for key={key!r}: {exc}"
            ) from exc
        except Exception as exc:
            raise MinioUnavailableError(
                f"MinIO unreachable during download (key={key!r}): {exc}"
            ) from exc

        _log.debug("minio.download", key=key, bytes=len(data))
        return data

    async def delete(self, key: str) -> None:
        """Remove the object at *key* from the bucket."""

        def _sync() -> None:
            self._client.remove_object(self._bucket, key)

        try:
            await asyncio.to_thread(_sync)
        except S3Error as exc:
            raise MinioUnavailableError(
                f"MinIO delete failed for key={key!r}: {exc}"
            ) from exc
        except Exception as exc:
            raise MinioUnavailableError(
                f"MinIO unreachable during delete (key={key!r}): {exc}"
            ) from exc

        _log.debug("minio.delete", key=key)

    async def health_check(self) -> dict[str, bool]:
        """Return ``{"minio": True}`` if the bucket is reachable, else ``{"minio": False}``."""

        def _sync() -> bool:
            return bool(self._client.bucket_exists(self._bucket))

        try:
            ok: bool = await asyncio.to_thread(_sync)
            return {"minio": ok}
        except Exception:
            return {"minio": False}
