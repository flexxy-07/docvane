import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from backend.app.db.models import Document, DocumentStatus
from backend.app.services.document import (
    MAX_FILE_SIZE_BYTES,
    VALID_TRANSITIONS,
    DocumentService,
    DocumentValidationError,
    InvalidStateTransitionError,
    compute_checksum,
)
from backend.app.services.storage import StorageService


def test_compute_checksum() -> None:
    data = b"Sample invoice content"
    checksum = compute_checksum(data)
    assert len(checksum) == 64
    assert checksum == compute_checksum(data)


def test_validate_file_success() -> None:
    service = DocumentService()
    ext = service.validate_file(
        filename="invoice_2026.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    assert ext == "pdf"


@pytest.mark.parametrize(
    "filename,content_type,size_bytes,expected_error",
    [
        (None, "application/pdf", 1024, "Document filename must be provided"),
        ("doc.pdf", "application/pdf", 0, "Uploaded document is empty"),
        (
            "huge.pdf",
            "application/pdf",
            MAX_FILE_SIZE_BYTES + 1,
            "File size exceeds maximum allowed limit",
        ),
        ("script.exe", "application/x-msdownload", 500, "Unsupported file extension"),
        ("file.pdf", "application/zip", 500, "Unsupported MIME type"),
    ],
)
def test_validate_file_failures(
    filename: str | None,
    content_type: str | None,
    size_bytes: int,
    expected_error: str,
) -> None:
    service = DocumentService()
    with pytest.raises(DocumentValidationError, match=expected_error):
        service.validate_file(filename, content_type, size_bytes)


def test_state_machine_transitions() -> None:
    # UPLOADED -> QUEUED is valid
    assert DocumentStatus.QUEUED in VALID_TRANSITIONS[DocumentStatus.UPLOADED]
    assert DocumentStatus.FAILED in VALID_TRANSITIONS[DocumentStatus.UPLOADED]
    # UPLOADED -> READY is invalid
    assert DocumentStatus.READY not in VALID_TRANSITIONS[DocumentStatus.UPLOADED]

    # EXTRACTING can go to NEEDS_REVIEW, INDEXING, or FAILED
    assert DocumentStatus.NEEDS_REVIEW in VALID_TRANSITIONS[DocumentStatus.EXTRACTING]
    assert DocumentStatus.INDEXING in VALID_TRANSITIONS[DocumentStatus.EXTRACTING]

    # FAILED can go to QUEUED (retry)
    assert DocumentStatus.QUEUED in VALID_TRANSITIONS[DocumentStatus.FAILED]


@pytest.mark.asyncio
async def test_transition_status_valid() -> None:
    mock_storage = MagicMock(spec=StorageService)
    service = DocumentService(storage_service=mock_storage)

    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="contract.pdf",
        file_type="pdf",
        status=DocumentStatus.UPLOADED,
        storage_key=f"{tenant_id}/{doc_id}/contract.pdf",
        checksum="abcd1234",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_result

    # 1. Valid transition: UPLOADED -> QUEUED
    updated_doc = await service.transition_status(
        session=mock_session,
        tenant_id=tenant_id,
        document_id=doc_id,
        new_status=DocumentStatus.QUEUED,
    )
    assert updated_doc.status == DocumentStatus.QUEUED
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_transition_status_invalid() -> None:
    mock_storage = MagicMock(spec=StorageService)
    service = DocumentService(storage_service=mock_storage)

    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="contract.pdf",
        file_type="pdf",
        status=DocumentStatus.UPLOADED,
        storage_key=f"{tenant_id}/{doc_id}/contract.pdf",
        checksum="abcd1234",
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_result

    # Illegal transition: UPLOADED -> READY
    with pytest.raises(InvalidStateTransitionError, match="Cannot transition document"):
        await service.transition_status(
            session=mock_session,
            tenant_id=tenant_id,
            document_id=doc_id,
            new_status=DocumentStatus.READY,
        )


@pytest.mark.asyncio
async def test_transition_status_failure_records_error() -> None:
    mock_storage = MagicMock(spec=StorageService)
    service = DocumentService(storage_service=mock_storage)

    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="invoice.pdf",
        file_type="pdf",
        status=DocumentStatus.PARSING,
        storage_key=f"{tenant_id}/{doc_id}/invoice.pdf",
        checksum="abcd1234",
        retry_count=0,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_result

    updated = await service.transition_status(
        session=mock_session,
        tenant_id=tenant_id,
        document_id=doc_id,
        new_status=DocumentStatus.FAILED,
        error_message="OCR engine timeout",
    )
    assert updated.status == DocumentStatus.FAILED
    assert updated.error_message == "OCR engine timeout"
    assert updated.retry_count == 1


@pytest.mark.asyncio
async def test_upload_document_deduplication() -> None:
    mock_storage = MagicMock(spec=StorageService)
    service = DocumentService(storage_service=mock_storage)

    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    content = b"%PDF-1.4 test invoice content"
    checksum = compute_checksum(content)

    existing_doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="existing_invoice.pdf",
        file_type="pdf",
        status=DocumentStatus.READY,
        storage_key=f"{tenant_id}/{doc_id}/existing_invoice.pdf",
        checksum=checksum,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_session.execute.return_value = mock_result

    from starlette.datastructures import Headers

    upload_file = UploadFile(
        file=io.BytesIO(content),
        filename="another_name.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    result_doc, is_duplicate = await service.upload_document(
        session=mock_session,
        tenant_id=tenant_id,
        file=upload_file,
    )

    assert is_duplicate is True
    assert result_doc.id == doc_id
    # Storage upload should NOT be invoked for duplicate documents
    mock_storage.upload_bytes.assert_not_called()
