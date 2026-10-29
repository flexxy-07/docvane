import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import Depends, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_storage
from backend.app.db.models import Document, DocumentStatus
from backend.app.services.storage import StorageService, build_storage_key

logger = logging.getLogger(__name__)

# Allowed MIME types and file extensions for uploaded documents
ALLOWED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB limit


class DocumentServiceError(Exception):
    """Base exception for document service errors."""

    pass


class DocumentValidationError(DocumentServiceError):
    """Raised when an uploaded document fails validation."""

    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a requested document does not exist."""

    pass


class InvalidStateTransitionError(DocumentServiceError):
    """Raised when attempting an unauthorized or invalid state transition."""

    pass


# State machine allowed transitions
VALID_TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.UPLOADED: {DocumentStatus.QUEUED, DocumentStatus.FAILED},
    DocumentStatus.QUEUED: {DocumentStatus.PARSING, DocumentStatus.FAILED},
    DocumentStatus.PARSING: {DocumentStatus.EXTRACTING, DocumentStatus.FAILED},
    DocumentStatus.EXTRACTING: {
        DocumentStatus.NEEDS_REVIEW,
        DocumentStatus.INDEXING,
        DocumentStatus.FAILED,
    },
    DocumentStatus.NEEDS_REVIEW: {DocumentStatus.REVIEWED, DocumentStatus.FAILED},
    DocumentStatus.REVIEWED: {DocumentStatus.INDEXING, DocumentStatus.FAILED},
    DocumentStatus.INDEXING: {DocumentStatus.READY, DocumentStatus.FAILED},
    DocumentStatus.READY: {DocumentStatus.INDEXING},  # Re-indexing trigger
    DocumentStatus.FAILED: {DocumentStatus.QUEUED},  # Retry / requeue trigger
}


def compute_checksum(data: bytes) -> str:
    """Computes SHA-256 hex digest for document deduplication and integrity check."""
    return hashlib.sha256(data).hexdigest()


class DocumentService:
    """Manages document uploads, deduplication, state transitions, and retrieval."""

    def __init__(self, storage_service: StorageService | None = None) -> None:
        self.storage = storage_service or StorageService()

    def validate_file(
        self,
        filename: str | None,
        content_type: str | None,
        size_bytes: int,
    ) -> str:
        """
        Validates file metadata, extension, MIME type, and size constraints.
        Returns the sanitized extension (e.g. 'pdf', 'png').
        """
        if not filename:
            raise DocumentValidationError("Document filename must be provided.")

        if size_bytes <= 0:
            raise DocumentValidationError("Uploaded document is empty (0 bytes).")

        if size_bytes > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            raise DocumentValidationError(
                f"File size exceeds maximum allowed limit of {max_mb:.0f} MB."
            )

        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise DocumentValidationError(
                f"Unsupported file extension '{suffix}'. Allowed extensions: {allowed}"
            )

        # Check content type if provided
        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
            allowed_types = ", ".join(sorted(ALLOWED_MIME_TYPES))
            raise DocumentValidationError(
                f"Unsupported MIME type '{content_type}'. Allowed types: {allowed_types}"
            )

        return suffix.lstrip(".")

    async def upload_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        file: UploadFile,
    ) -> tuple[Document, bool]:
        """
        Processes an incoming uploaded file for a tenant:
        1. Reads and validates content size, extension, and content type.
        2. Computes the SHA-256 checksum.
        3. Checks for duplicate uploads within the same tenant (deduplication).
        4. If unique: stores file in object storage and creates the DB record.
        Returns a tuple of (Document, is_duplicate).
        """
        content = await file.read()
        filename = file.filename or "uploaded_document"
        clean_filename = Path(filename).name

        ext = self.validate_file(
            filename=clean_filename,
            content_type=file.content_type,
            size_bytes=len(content),
        )

        checksum = compute_checksum(content)

        # Check for duplicate document in tenant scope
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.checksum == checksum,
        )
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            logger.info(
                "Duplicate document upload detected",
                extra={
                    "tenant_id": str(tenant_id),
                    "document_id": str(existing_doc.id),
                    "checksum": checksum,
                },
            )
            return existing_doc, True

        document_id = uuid.uuid4()
        storage_key = build_storage_key(tenant_id, document_id, clean_filename)

        # Upload file content to object storage
        self.storage.upload_bytes(
            data=content,
            key=storage_key,
            content_type=file.content_type or "application/octet-stream",
        )

        # Create database record
        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            filename=clean_filename,
            file_type=ext,
            status=DocumentStatus.UPLOADED,
            storage_key=storage_key,
            checksum=checksum,
            file_size_bytes=len(content),
            page_count=0,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)

        logger.info(
            "Document created successfully",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document.id),
                "storage_key": storage_key,
            },
        )
        return document, False

    async def get_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        """
        Retrieves a single document scoped by tenant_id.
        Raises DocumentNotFoundError if missing.
        """
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.id == document_id,
        )
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise DocumentNotFoundError(
                f"Document with ID '{document_id}' not found for this tenant."
            )
        return doc

    async def list_documents(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        status: DocumentStatus | None = None,
    ) -> tuple[list[Document], int]:
        """Returns a paginated list of documents and total count for a tenant."""
        base_filter = [Document.tenant_id == tenant_id]
        if status:
            base_filter.append(Document.status == status)

        count_stmt = select(func.count()).select_from(Document).where(*base_filter)
        total = (await session.execute(count_stmt)).scalar_one()

        items_stmt = (
            select(Document)
            .where(*base_filter)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(items_stmt)
        items = list(result.scalars().all())

        return items, total

    async def transition_status(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        new_status: DocumentStatus,
        error_message: str | None = None,
    ) -> Document:
        """
        Validates and transitions a document's status based on the defined state machine.
        Raises InvalidStateTransitionError if the requested transition is illegal.
        """
        doc = await self.get_document(session, tenant_id, document_id)
        allowed = VALID_TRANSITIONS.get(doc.status, set())

        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition document '{document_id}' from status '{doc.status}' "
                f"to '{new_status}'. Allowed transitions: {[s.value for s in allowed]}"
            )

        doc.status = new_status
        if new_status == DocumentStatus.FAILED:
            doc.error_message = error_message
            doc.retry_count += 1
        elif error_message is not None:
            doc.error_message = error_message

        await session.commit()
        await session.refresh(doc)

        logger.info(
            "Document status transitioned",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "new_status": new_status.value,
            },
        )
        return doc

    async def delete_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        """
        Deletes document record from database and removes associated binary from object storage.
        """
        doc = await self.get_document(session, tenant_id, document_id)

        # Attempt to delete file from object storage
        try:
            self.storage.delete_file(doc.storage_key)
        except Exception as e:
            logger.warning(
                "Failed to delete document from storage during document removal",
                extra={"storage_key": doc.storage_key, "error": str(e)},
            )

        await session.delete(doc)
        await session.commit()
        logger.info(
            "Document deleted successfully",
            extra={"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )

    def get_download_url(self, document: Document, expires_in: int = 3600) -> str:
        """Generates a secure download/viewing URL for the document."""
        url = self.storage.generate_presigned_url(document.storage_key, expires_in=expires_in)
        return str(url)


def get_document_service(
    storage_service: StorageService = Depends(get_storage),
) -> DocumentService:
    """FastAPI dependency provider for DocumentService."""
    return DocumentService(storage_service=storage_service)
