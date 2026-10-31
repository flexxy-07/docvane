import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pypdf import PdfWriter

from backend.app.db.models import Document, DocumentPage, DocumentStatus
from backend.app.workers.tasks import (
    _async_index_document,
    _async_process_document,
    process_document,
    split_pdf_into_pages,
)


def _generate_sample_pdf(num_pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_pdf_into_pages() -> None:
    pdf_bytes = _generate_sample_pdf(num_pages=3)
    pages = split_pdf_into_pages(pdf_bytes)

    assert len(pages) == 3
    # Check 1-indexed page numbering
    assert pages[0][0] == 1
    assert pages[1][0] == 2
    assert pages[2][0] == 3
    # Each page has non-empty bytes
    assert len(pages[0][1]) > 0


@pytest.mark.asyncio
async def test_async_process_document_success() -> None:
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    pdf_data = _generate_sample_pdf(num_pages=2)

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="report.pdf",
        file_type="pdf",
        status=DocumentStatus.UPLOADED,
        storage_key=f"{tenant_id}/{doc_id}/report.pdf",
        checksum="dummy_checksum",
        file_size_bytes=len(pdf_data),
        page_count=0,
    )

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = pdf_data

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_result

    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_classification = MagicMock()
    mock_classification.doc_type.value = "other"

    with (
        patch("backend.app.workers.tasks.StorageService", return_value=mock_storage),
        patch("backend.app.workers.tasks.AsyncSessionLocal", return_value=mock_context),
        patch(
            "backend.app.services.extraction.ExtractionService.classify_document",
            return_value=mock_classification,
        ),
    ):
        result = await _async_process_document(str(doc_id), str(tenant_id))

    assert result["document_id"] == str(doc_id)
    assert result["page_count"] == 2
    assert doc.status == DocumentStatus.INDEXING
    assert doc.page_count == 2
    # Storage should have received 2 uploaded page files
    assert mock_storage.upload_bytes.call_count == 2


@pytest.mark.asyncio
async def test_async_process_document_image() -> None:
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    image_data = b"fake-png-bytes"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="receipt.png",
        file_type="png",
        status=DocumentStatus.QUEUED,
        storage_key=f"{tenant_id}/{doc_id}/receipt.png",
        checksum="dummy_checksum",
        file_size_bytes=len(image_data),
        page_count=0,
    )

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = image_data

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_result

    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_classification = MagicMock()
    mock_classification.doc_type.value = "other"

    with (
        patch("backend.app.workers.tasks.StorageService", return_value=mock_storage),
        patch("backend.app.workers.tasks.AsyncSessionLocal", return_value=mock_context),
        patch(
            "backend.app.services.extraction.ExtractionService.classify_document",
            return_value=mock_classification,
        ),
    ):
        result = await _async_process_document(str(doc_id), str(tenant_id))

    assert result["page_count"] == 1
    assert doc.status == DocumentStatus.INDEXING
    assert doc.page_count == 1
    assert mock_storage.upload_bytes.call_count == 1


def test_celery_task_retry_and_failure() -> None:
    doc_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    with (
        patch(
            "backend.app.workers.tasks._async_process_document",
            side_effect=ValueError("Corrupt PDF file"),
        ),
        patch("backend.app.workers.tasks._mark_document_failed") as mock_mark_failed,
        patch.object(process_document, "retry", side_effect=RuntimeError("Retry triggered")),
    ):
        process_document.request.retries = 3
        process_document.max_retries = 3
        with pytest.raises(RuntimeError, match="Retry triggered"):
            process_document.run(doc_id, tenant_id)

    # Verify mark failed helper was triggered on final retry
    mock_mark_failed.assert_called_once()


@pytest.mark.asyncio
async def test_async_index_document() -> None:
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="contract.pdf",
        file_type="pdf",
        status=DocumentStatus.INDEXING,
        storage_key=f"{tenant_id}/{doc_id}/contract.pdf",
        checksum="checksum123",
        file_size_bytes=2048,
        page_count=1,
    )

    page = DocumentPage(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        page_no=1,
        ocr_text=(
            "Section 1. Agreement Terms\n\nThis agreement is made between Party A and Party B."
        ),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # Query 1: fetch doc
    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = doc

    # Query 2: fetch pages
    pages_res = MagicMock()
    pages_res.scalars.return_value.all.return_value = [page]

    # Query 3: delete previous chunks
    del_res = MagicMock()

    mock_session.execute.side_effect = [
        MagicMock(),  # set_config
        doc_res,      # select doc
        pages_res,    # select pages
        del_res,      # delete chunks
        doc_res,      # transition_status select doc
    ]

    mock_context = MagicMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    with patch("backend.app.workers.tasks.AsyncSessionLocal", return_value=mock_context):
        result = await _async_index_document(str(doc_id), str(tenant_id))

    assert result["document_id"] == str(doc_id)
    assert result["status"] == "ready"
    assert result["chunk_count"] >= 1
    assert doc.status == DocumentStatus.READY
    assert mock_session.add.called

