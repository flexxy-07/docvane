import asyncio
import io
import logging
import uuid
from typing import Any

from pypdf import PdfReader, PdfWriter
from sqlalchemy import delete, select, text

from backend.app.db.models import Document, DocumentChunk, DocumentPage, DocumentStatus
from backend.app.db.session import AsyncSessionLocal
from backend.app.services.chunking import ChunkPayload, LayoutAwareChunker
from backend.app.services.document import DocumentService
from backend.app.services.embedding import EmbeddingService
from backend.app.services.storage import StorageService
from backend.app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def split_pdf_into_pages(pdf_bytes: bytes) -> list[tuple[int, bytes, str | None]]:
    """
    Splits a PDF byte-stream into individual single-page PDF byte-streams.
    Returns a list of (page_number, single_page_pdf_bytes, extracted_text).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages: list[tuple[int, bytes, str | None]] = []

    for idx, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)

        buffer = io.BytesIO()
        writer.write(buffer)
        page_bytes = buffer.getvalue()

        # Extracts whatever direct text is embedded (if any)
        raw_text = page.extract_text() or None
        page_no = idx + 1
        pages.append((page_no, page_bytes, raw_text))

    return pages


async def _async_process_document(document_id_str: str, tenant_id_str: str) -> dict[str, Any]:
    """
    Asynchronous core logic to ingest and parse a document:
    1. Sets tenant context for RLS in PostgreSQL.
    2. Transitions status: UPLOADED -> QUEUED -> PARSING.
    3. Downloads raw file from storage and splits into pages.
    4. Saves each page and its single-page file in storage.
    5. Creates DocumentPage records in DB.
    6. Transitions status: PARSING -> EXTRACTING.
    """
    document_id = uuid.UUID(document_id_str)
    tenant_id = uuid.UUID(tenant_id_str)

    storage = StorageService()
    doc_service = DocumentService(storage_service=storage)

    async with AsyncSessionLocal() as session:
        # Enforcing PostgreSQL row-level security
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )

        doc = await doc_service.get_document(session, tenant_id, document_id)
        if doc.status == DocumentStatus.UPLOADED:
            doc = await doc_service.transition_status(
                session, tenant_id, document_id, DocumentStatus.QUEUED
            )

        # 2. Transition: QUEUED -> PARSING
        doc = await doc_service.transition_status(
            session, tenant_id, document_id, DocumentStatus.PARSING
        )

        # 3. Fetch file from storage
        file_bytes = storage.download_bytes(doc.storage_key)

        # 4. Split into pages
        pages_to_create: list[tuple[int, bytes, str | None]] = []
        is_pdf = doc.file_type == "pdf" or doc.filename.lower().endswith(".pdf")

        if is_pdf:
            pages_to_create = split_pdf_into_pages(file_bytes)
        else:
            # Single image page: treated as 1-page document
            pages_to_create.append((1, file_bytes, None))

        # 5. Persist page files & DocumentPage records with hybrid OCR
        from backend.app.services.ocr import OCRService

        ocr_service = OCRService()

        for page_no, page_data, direct_text in pages_to_create:
            page_ext = "pdf" if is_pdf else doc.file_type
            page_storage_key = f"{tenant_id}/{document_id}/pages/page_{page_no}.{page_ext}"
            content_type = "application/pdf" if is_pdf else f"image/{doc.file_type}"
            storage.upload_bytes(page_data, page_storage_key, content_type=content_type)

            # Parse with hybrid OCR (Fast-path direct text or Vision LLM fallback)
            ocr_result = ocr_service.parse_page(
                page_bytes=page_data,
                mime_type=content_type,
                existing_text=direct_text,
            )

            page_model = DocumentPage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                page_no=page_no,
                image_storage_key=page_storage_key,
                ocr_text=ocr_result.text,
                layout_json=ocr_result.layout_json,
                ocr_engine=ocr_result.engine,
                used_vision_fallback=ocr_result.used_vision_fallback,
            )
            session.add(page_model)

        # 6. Update total page count on Document record
        doc.page_count = len(pages_to_create)

        # 7. Transition: PARSING -> EXTRACTING
        doc = await doc_service.transition_status(
            session, tenant_id, document_id, DocumentStatus.EXTRACTING
        )

        # 8. Run Document Classification & Extraction
        from backend.app.db.models import Contract, ExtractedFieldModel, FieldStatus, Invoice
        from backend.app.schemas.extraction import DocumentType
        from backend.app.services.extraction import ExtractionService

        extraction_service = ExtractionService()

        # Combine text across all pages for full document understanding
        full_text = "\n\n".join(
            [text_part for _, _, text_part in pages_to_create if text_part]
        )

        classification = extraction_service.classify_document(full_text)
        doc.doc_type = classification.doc_type.value

        any_low_confidence = False
        CONFIDENCE_THRESHOLD = 0.85

        if classification.doc_type == DocumentType.INVOICE:
            inv = extraction_service.extract_invoice(full_text)

            # Persist typed invoice table for Text-to-SQL (Phase 8)
            invoice_record = Invoice(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                vendor_name=inv.vendor_name.value,
                customer_name=inv.customer_name.value,
                invoice_number=inv.invoice_number.value,
                invoice_date=inv.invoice_date.value,
                due_date=inv.due_date.value,
                currency=inv.currency.value or "USD",
                subtotal=inv.subtotal.value,
                tax_amount=inv.tax_amount.value,
                total_amount=inv.total_amount.value,
                line_items=[item.model_dump() for item in inv.line_items],
            )
            session.add(invoice_record)

            # Persist extracted_fields for human review queue & auditing (Phase 3)
            for field_name in [
                "vendor_name",
                "customer_name",
                "invoice_number",
                "invoice_date",
                "due_date",
                "total_amount",
            ]:
                extracted_item = getattr(inv, field_name)
                is_low = extracted_item.confidence < CONFIDENCE_THRESHOLD
                if is_low:
                    any_low_confidence = True

                field_id = uuid.uuid4()
                session.add(
                    ExtractedFieldModel(
                        id=field_id,
                        tenant_id=tenant_id,
                        document_id=document_id,
                        field_name=field_name,
                        field_value=str(extracted_item.value)
                        if extracted_item.value is not None
                        else None,
                        confidence=extracted_item.confidence,
                        source_page=extracted_item.page_no,
                        bbox=extracted_item.bbox,
                        status=FieldStatus.NEEDS_REVIEW if is_low else FieldStatus.AUTO,
                    )
                )

                if is_low:
                    from backend.app.db.models import ReviewStatus, ReviewTask

                    session.add(
                        ReviewTask(
                            id=uuid.uuid4(),
                            tenant_id=tenant_id,
                            document_id=document_id,
                            field_id=field_id,
                            status=ReviewStatus.PENDING,
                        )
                    )

        elif classification.doc_type == DocumentType.CONTRACT:
            contract_data = extraction_service.extract_contract(full_text)

            contract_record = Contract(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                title=contract_data.title.value,
                parties=contract_data.parties,
                effective_date=contract_data.effective_date.value,
                expiration_date=contract_data.expiration_date.value,
                term_length=contract_data.term_length.value,
                governing_law=contract_data.governing_law.value,
            )
            session.add(contract_record)

            for field_name in ["title", "effective_date", "expiration_date", "governing_law"]:
                extracted_item = getattr(contract_data, field_name)
                is_low = extracted_item.confidence < CONFIDENCE_THRESHOLD
                if is_low:
                    any_low_confidence = True

                field_id = uuid.uuid4()
                session.add(
                    ExtractedFieldModel(
                        id=field_id,
                        tenant_id=tenant_id,
                        document_id=document_id,
                        field_name=field_name,
                        field_value=str(extracted_item.value)
                        if extracted_item.value is not None
                        else None,
                        confidence=extracted_item.confidence,
                        source_page=extracted_item.page_no,
                        bbox=extracted_item.bbox,
                        status=FieldStatus.NEEDS_REVIEW if is_low else FieldStatus.AUTO,
                    )
                )

                if is_low:
                    from backend.app.db.models import ReviewStatus, ReviewTask

                    session.add(
                        ReviewTask(
                            id=uuid.uuid4(),
                            tenant_id=tenant_id,
                            document_id=document_id,
                            field_id=field_id,
                            status=ReviewStatus.PENDING,
                        )
                    )

        # 9. Status transition based on extraction confidence:
        # If low confidence -> NEEDS_REVIEW (Phase 3 review queue)
        # If all high confidence -> INDEXING (Phase 4 chunking/vector search)
        next_status = (
            DocumentStatus.NEEDS_REVIEW if any_low_confidence else DocumentStatus.INDEXING
        )
        doc = await doc_service.transition_status(session, tenant_id, document_id, next_status)

        await session.commit()

        if next_status == DocumentStatus.INDEXING:
            try:
                index_document.delay(str(document_id), str(tenant_id))
            except Exception as exc:
                logger.warning(
                    "Could not dispatch index_document task: %s",
                    str(exc),
                )

        logger.info(
            "Document parsed and extracted successfully",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "doc_type": doc.doc_type,
                "status": doc.status.value,
            },
        )

        return {
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "doc_type": doc.doc_type,
            "status": doc.status.value,
            "page_count": doc.page_count,
        }


@celery_app.task(bind=True, max_retries=3, name="process_document")  # type: ignore[untyped-decorator]
def process_document(self: Any, document_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Celery task entry point with automatic exponential backoff retry:
    - Attempt 1: retry after 2s
    - Attempt 2: retry after 4s
    - Attempt 3: retry after 8s -> marks document FAILED if all retries exhausted.
    """
    try:
        return asyncio.run(_async_process_document(document_id, tenant_id))
    except Exception as exc:
        logger.error(
            "Error processing document",
            extra={
                "document_id": document_id,
                "error": str(exc),
                "retry": self.request.retries,
            },
        )

        if self.request.retries >= self.max_retries:
            # Final failure handling: mark document status as FAILED in DB
            try:
                asyncio.run(_mark_document_failed(document_id, tenant_id, str(exc)))
            except Exception as mark_error:
                logger.error(
                    "Failed to mark document as failed",
                    extra={"error": str(mark_error)},
                )
        countdown = 2**self.request.retries
        raise self.retry(exc=exc, countdown=countdown) from exc


async def _mark_document_failed(
    document_id_str: str,
    tenant_id_str: str,
    error_msg: str,
) -> None:
    """Helper to update document status to FAILED upon final task error."""
    document_id = uuid.UUID(document_id_str)
    tenant_id = uuid.UUID(tenant_id_str)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.id == document_id,
        )
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = error_msg
            doc.retry_count += 1
            await session.commit()


async def _async_index_document(document_id_str: str, tenant_id_str: str) -> dict[str, Any]:
    """
    Asynchronous core logic to chunk document pages and store vector embeddings:
    1. Loads all pages with OCR text.
    2. Runs layout-aware chunker (preserving tables & headers).
    3. Generates dense 768-d vector embeddings in batches.
    4. Writes DocumentChunk records with pgvector embeddings to PostgreSQL.
    5. Transitions document status from INDEXING -> READY.
    """
    document_id = uuid.UUID(document_id_str)
    tenant_id = uuid.UUID(tenant_id_str)
    chunker = LayoutAwareChunker()
    embedding_service = EmbeddingService()
    doc_service = DocumentService()

    async with AsyncSessionLocal() as session:
        # Enforce PostgreSQL tenant isolation
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )

        # 1. Fetch document
        doc_stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.id == document_id,
        )
        doc = (await session.execute(doc_stmt)).scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 2. Fetch pages ordered by page_no
        pages_stmt = (
            select(DocumentPage)
            .where(
                DocumentPage.tenant_id == tenant_id,
                DocumentPage.document_id == document_id,
            )
            .order_by(DocumentPage.page_no.asc())
        )
        pages = list((await session.execute(pages_stmt)).scalars().all())

        page_data = [(p.page_no, p.ocr_text or "") for p in pages]
        chunks = chunker.chunk_document_pages(page_data, filename=doc.filename)

        if not chunks:
            chunks = [
                ChunkPayload(
                    chunk_index=0,
                    page_number=1 if pages else None,
                    chunk_type="text",
                    content=f"[Document: {doc.filename}]\nEmpty document content.",
                    metadata_json={"filename": doc.filename, "empty": True},
                )
            ]

        # 3. Generate embeddings
        chunk_texts = [c.content for c in chunks]
        embeddings = embedding_service.embed_texts(chunk_texts)

        # 4. Remove previous chunks for this document (idempotent re-indexing)
        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_id == document_id,
            )
        )

        # 5. Insert DocumentChunk records
        for i, chunk in enumerate(chunks):
            embedding_vector = embeddings[i] if i < len(embeddings) else None
            chunk_record = DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                metadata_json=chunk.metadata_json,
                embedding=embedding_vector,
            )
            session.add(chunk_record)

        # 6. Transition document status from INDEXING -> READY
        doc = await doc_service.transition_status(
            session, tenant_id, document_id, DocumentStatus.READY
        )
        await session.commit()

        logger.info(
            "Document indexed successfully",
            extra={
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "chunks_count": len(chunks),
                "status": doc.status.value,
            },
        )

        return {
            "document_id": str(document_id),
            "tenant_id": str(tenant_id),
            "status": doc.status.value,
            "chunk_count": len(chunks),
        }


@celery_app.task(bind=True, max_retries=3, name="index_document")  # type: ignore[untyped-decorator]
def index_document(self: Any, document_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Celery task entry point with automatic exponential backoff retry for vector indexing:
    - Attempt 1: retry after 2s
    - Attempt 2: retry after 4s
    - Attempt 3: retry after 8s -> marks document FAILED if all retries exhausted.
    """
    try:
        return asyncio.run(_async_index_document(document_id, tenant_id))
    except Exception as exc:
        logger.error(
            "Error indexing document",
            extra={
                "document_id": document_id,
                "error": str(exc),
                "retry": self.request.retries,
            },
        )

        if self.request.retries >= self.max_retries:
            try:
                asyncio.run(_mark_document_failed(document_id, tenant_id, str(exc)))
            except Exception as mark_error:
                logger.error(
                    "Failed to mark document as failed",
                    extra={"error": str(mark_error)},
                )
        countdown = 2**self.request.retries
        raise self.retry(exc=exc, countdown=countdown) from exc

