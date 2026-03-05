"""Unit tests for MinioFileStore — mocks Minio client and asyncio.to_thread."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from reasoner.config import Settings
from reasoner.rag.adapters.minio import MinioFileStore, MinioUnavailableError


def _settings() -> Settings:
    return Settings(
        SHERLOCK_POSTGRES_URL="postgresql+asyncpg://arc:arc@localhost/arc",
        SHERLOCK_RAG_ENABLED=True,
    )


def _store_with_mock_client() -> tuple[MinioFileStore, MagicMock]:
    """Return a MinioFileStore with a mocked Minio client."""
    with patch("reasoner.rag.adapters.minio.Minio") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        store = MinioFileStore(_settings())
        store._client = mock_client
    return store, mock_client


async def _run_to_thread(func):  # type: ignore[no-untyped-def]
    """Execute the sync callable directly (replaces asyncio.to_thread in tests)."""
    return func()


class TestMinioFileStoreUpload:
    async def test_upload_success(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.return_value = True

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            await store.upload("key-1", b"hello", "text/plain")

        client.put_object.assert_called_once()

    async def test_upload_creates_bucket_when_missing(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.return_value = False

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            await store.upload("key-1", b"data", "text/plain")

        client.make_bucket.assert_called_once_with(store._bucket)

    async def test_upload_s3error_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.return_value = True
        client.put_object.side_effect = S3Error(
            "NoSuchBucket", "bucket missing", "res", "req", MagicMock(), MagicMock()
        )

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="upload failed"),
        ):
            await store.upload("key-bad", b"x", "text/plain")

    async def test_upload_oserror_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.side_effect = OSError("connection refused")

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="unreachable"),
        ):
            await store.upload("key-bad", b"x", "text/plain")


class TestMinioFileStoreDownload:
    async def test_download_returns_bytes(self) -> None:
        store, client = _store_with_mock_client()
        response = MagicMock()
        response.read.return_value = b"file content"
        client.get_object.return_value = response

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            data = await store.download("key-1")

        assert data == b"file content"
        response.close.assert_called_once()

    async def test_download_s3error_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.get_object.side_effect = S3Error(
            "NoSuchKey", "key missing", "res", "req", MagicMock(), MagicMock()
        )

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="download failed"),
        ):
            await store.download("missing-key")

    async def test_download_oserror_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.get_object.side_effect = OSError("timeout")

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="unreachable"),
        ):
            await store.download("key-bad")


class TestMinioFileStoreDelete:
    async def test_delete_success(self) -> None:
        store, client = _store_with_mock_client()

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            await store.delete("key-1")

        client.remove_object.assert_called_once_with(store._bucket, "key-1")

    async def test_delete_s3error_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.remove_object.side_effect = S3Error(
            "Err", "err", "res", "req", MagicMock(), MagicMock()
        )

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="delete failed"),
        ):
            await store.delete("key-bad")

    async def test_delete_oserror_raises_minio_unavailable(self) -> None:
        store, client = _store_with_mock_client()
        client.remove_object.side_effect = OSError("broken pipe")

        with (
            patch("asyncio.to_thread", side_effect=_run_to_thread),
            pytest.raises(MinioUnavailableError, match="unreachable"),
        ):
            await store.delete("key-bad")


class TestMinioFileStoreHealthCheck:
    async def test_health_check_returns_true_when_bucket_exists(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.return_value = True

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            result = await store.health_check()

        assert result == {"minio": True}

    async def test_health_check_returns_false_when_bucket_missing(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.return_value = False

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            result = await store.health_check()

        assert result == {"minio": False}

    async def test_health_check_returns_false_on_s3error(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.side_effect = S3Error(
            "Err", "err", "res", "req", MagicMock(), MagicMock()
        )

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            result = await store.health_check()

        assert result == {"minio": False}

    async def test_health_check_returns_false_on_oserror(self) -> None:
        store, client = _store_with_mock_client()
        client.bucket_exists.side_effect = OSError("unreachable")

        with patch("asyncio.to_thread", side_effect=_run_to_thread):
            result = await store.health_check()

        assert result == {"minio": False}
