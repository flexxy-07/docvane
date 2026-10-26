import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.app.core.config import Settings
from backend.app.services.storage import (
    StorageError,
    StorageFileNotFoundError,
    StorageService,
    build_storage_key,
)


@pytest.fixture
def s3_settings() -> Settings:
    return Settings(
        S3_ENDPOINT_URL="https://mock-endpoint.r2.cloudflarestorage.com",
        S3_ACCESS_KEY_ID="mock-key",
        S3_SECRET_ACCESS_KEY="mock-secret",
        S3_BUCKET_NAME="test-bucket",
    )


def test_build_storage_key() -> None:
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    filename = "invoice 2026.pdf"

    key = build_storage_key(tenant_id, doc_id, filename)
    assert key == f"{tenant_id}/{doc_id}/invoice 2026.pdf"

    # Sanitization check
    path_traversal = "../../bad_path/file.pdf"
    clean_key = build_storage_key(tenant_id, doc_id, path_traversal)
    assert "/" not in clean_key.split("/", 2)[2]


def test_storage_local_filesystem(tmp_path: Path) -> None:
    """Verifies that local filesystem storage operates correctly offline."""
    local_settings = Settings(S3_ENDPOINT_URL="local")
    service = StorageService(app_settings=local_settings)
    service.local_dir = tmp_path

    test_data = b"Hello Docvane local file content"
    key = "tenant-abc/doc-123/sample.txt"

    # 1. Upload (writes to local path)
    saved_key = service.upload_bytes(test_data, key)
    assert saved_key == key
    assert (tmp_path / key).is_file()

    # 2. File exists check
    assert service.file_exists(key) is True
    assert service.file_exists("nonexistent.txt") is False

    # 3. Download
    downloaded = service.download_bytes(key)
    assert downloaded == test_data

    # 4. Presigned URL in local mode
    url = service.generate_presigned_url(key)
    assert url == f"/api/v1/documents/raw/{key}"

    # 5. Delete
    assert service.delete_file(key) is True
    assert (tmp_path / key).exists() is False

    # 6. Not found error
    with pytest.raises(StorageFileNotFoundError):
        service.download_bytes("nonexistent.txt")


@patch("boto3.client")
def test_storage_s3_upload_bytes(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    service = StorageService(app_settings=s3_settings)
    test_data = b"%PDF-1.4 test invoice content"
    key = "tenant-1/doc-1/test.pdf"

    result_key = service.upload_bytes(test_data, key, content_type="application/pdf")

    assert result_key == key
    mock_s3.put_object.assert_called_once_with(
        Bucket=service.bucket,
        Key=key,
        Body=test_data,
        ContentType="application/pdf",
    )


@patch("boto3.client")
def test_storage_s3_download_bytes(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    mock_body = MagicMock()
    mock_body.read.return_value = b"sample pdf content"
    mock_s3.get_object.return_value = {"Body": mock_body}

    service = StorageService(app_settings=s3_settings)
    data = service.download_bytes("tenant-1/doc-1/file.pdf")

    assert data == b"sample pdf content"
    mock_s3.get_object.assert_called_once_with(
        Bucket=service.bucket, Key="tenant-1/doc-1/file.pdf"
    )


@patch("boto3.client")
def test_storage_s3_download_not_found(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    mock_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
        "GetObject",
    )

    service = StorageService(app_settings=s3_settings)
    with pytest.raises(StorageFileNotFoundError):
        service.download_bytes("missing.pdf")


@patch("boto3.client")
def test_storage_s3_file_exists(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    service = StorageService(app_settings=s3_settings)

    # Exists
    mock_s3.head_object.return_value = {}
    assert service.file_exists("existing.pdf") is True

    # Does not exist
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadObject",
    )
    assert service.file_exists("missing.pdf") is False


@patch("boto3.client")
def test_storage_s3_delete_file(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    service = StorageService(app_settings=s3_settings)
    success = service.delete_file("tenant-1/doc-1/file.pdf")

    assert success is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket=service.bucket, Key="tenant-1/doc-1/file.pdf"
    )


@patch("boto3.client")
def test_storage_s3_error_handling(mock_boto_client: MagicMock, s3_settings: Settings) -> None:
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3
    mock_s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "InternalError", "Message": "S3 failure"}},
        "PutObject",
    )

    service = StorageService(app_settings=s3_settings)
    with pytest.raises(StorageError):
        service.upload_bytes(b"data", "key.pdf")
