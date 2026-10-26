import io
import logging
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from backend.app.core.config import Settings, settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for all object storage operations."""

    pass


class StorageFileNotFoundError(StorageError):
    """Raised when a requested object is not found in storage."""

    pass


def build_storage_key(
    tenant_id: uuid.UUID | str,
    document_id: uuid.UUID | str,
    filename: str,
) -> str:
    """Builds a deterministic, tenant-partitioned storage key for object storage."""
    safe_filename = filename.replace("\\", "_").replace("/", "_").strip()
    return f"{tenant_id}/{document_id}/{safe_filename}"


class StorageService:
    """Manages file storage operations on S3 / Cloudflare R2."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.bucket = self.settings.S3_BUCKET_NAME
        self.is_local = self.settings.S3_ENDPOINT_URL.strip().lower() in ("local", "")
        self.local_dir = Path("uploads")

        if not self.is_local:
            client_kwargs: dict[str, Any] = {
                "service_name": "s3",
                "aws_access_key_id": self.settings.S3_ACCESS_KEY_ID,
                "aws_secret_access_key": self.settings.S3_SECRET_ACCESS_KEY,
                "region_name": self.settings.S3_REGION,
                "config": Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            }

            if self.settings.S3_ENDPOINT_URL:
                client_kwargs["endpoint_url"] = self.settings.S3_ENDPOINT_URL

            self.client = boto3.client(**client_kwargs)

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Uploads raw bytes to storage (local filesystem or S3)."""
        if self.is_local:
            target = self.local_dir / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            logger.info(
                "Saved file to local storage",
                extra={"storage_key": key, "bytes": len(data)},
            )
            return key

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info("Uploaded file to storage", extra={"storage_key": key, "bytes": len(data)})
            return key
        except ClientError as e:
            logger.error(
                "Failed to upload file to storage",
                extra={"storage_key": key, "error": str(e)},
            )
            raise StorageError(f"Failed to upload {key}: {e}") from e

    def download_bytes(self, key: str) -> bytes:
        """Downloads object bytes from storage."""
        if self.is_local:
            target = self.local_dir / key
            if not target.is_file():
                raise StorageFileNotFoundError(f"Object {key} not found")
            return target.read_bytes()

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body: io.BytesIO = response["Body"]
            return body.read()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                raise StorageFileNotFoundError(f"Object {key} not found") from e
            logger.error(
                "Failed to download file from storage",
                extra={"storage_key": key, "error": str(e)},
            )
            raise StorageError(f"Failed to download {key}: {e}") from e

    def file_exists(self, key: str) -> bool:
        """Checks if a file exists in the bucket or local directory."""
        if self.is_local:
            return (self.local_dir / key).is_file()

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                return False
            raise StorageError(f"Error checking file existence for {key}: {e}") from e

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generates a temporary URL for viewing in browser/UI."""
        if self.is_local:
            return f"/api/v1/documents/raw/{key}"

        try:
            url: str = self.client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(
                "Failed to generate presigned URL",
                extra={"storage_key": key, "error": str(e)},
            )
            raise StorageError(f"Failed to generate presigned URL for {key}: {e}") from e

    def delete_file(self, key: str) -> bool:
        """Deletes an object from storage."""
        if self.is_local:
            target = self.local_dir / key
            if target.is_file():
                target.unlink()
                logger.info("Deleted file from local storage", extra={"storage_key": key})
            return True

        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info("Deleted file from storage", extra={"storage_key": key})
            return True
        except ClientError as e:
            logger.error(
                "Failed to delete file from storage",
                extra={"storage_key": key, "error": str(e)},
            )
            raise StorageError(f"Failed to delete {key}: {e}") from e


def get_storage_service() -> StorageService:
    """Dependency provider for FastAPI route injection."""
    return StorageService()
