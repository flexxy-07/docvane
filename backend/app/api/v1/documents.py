import mimetypes
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_tenant_id, get_storage, get_tenant_db
from backend.app.db.models import Document, DocumentStatus
from backend.app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from backend.app.services.document import (
    DocumentNotFoundError,
    DocumentService,
    DocumentValidationError,
    get_document_service,
)
from backend.app.services.storage import StorageError, StorageFileNotFoundError, StorageService

router = APIRouter(prefix="/documents", tags=["documents"])


def _to_document_response(doc: Document, service: DocumentService) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        filename=doc.filename,
        file_type=doc.file_type,
        doc_type=doc.doc_type,
        status=doc.status,
        storage_key=doc.storage_key,
        checksum=doc.checksum,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        error_message=doc.error_message,
        retry_count=doc.retry_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        download_url=service.get_download_url(doc),
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document",
)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
    """
    Upload a document (PDF or image).
    Performs content-type and size validation, SHA-256 deduplication,
    stores the raw file in object storage, and creates a document record.
    """
    try:
        doc, is_duplicate = await service.upload_document(
            session=session,
            tenant_id=tenant_id,
            file=file,
        )
        return DocumentUploadResponse(
            id=doc.id,
            tenant_id=doc.tenant_id,
            filename=doc.filename,
            file_type=doc.file_type,
            status=doc.status,
            storage_key=doc.storage_key,
            checksum=doc.checksum,
            file_size_bytes=doc.file_size_bytes,
            page_count=doc.page_count,
            is_duplicate=is_duplicate,
            created_at=doc.created_at,
        )
    except DocumentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage operation failed: {e}",
        ) from e


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List tenant documents",
)
async def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    doc_status: DocumentStatus | None = Query(default=None, alias="status"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """Retrieves a paginated list of documents belonging to the authenticated tenant."""
    items, total = await service.list_documents(
        session=session,
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        status=doc_status,
    )
    return DocumentListResponse(
        items=[_to_document_response(doc, service) for doc in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
)
async def get_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """Retrieves details of a single document including pre-signed download URL."""
    try:
        doc = await service.get_document(
            session=session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        return _to_document_response(doc, service)
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    service: DocumentService = Depends(get_document_service),
) -> None:
    """Deletes a document from both database and underlying object storage."""
    try:
        await service.delete_document(
            session=session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/raw/{key:path}",
    summary="Download raw document object (Local storage mode)",
)
def get_raw_document(
    key: str,
    storage: StorageService = Depends(get_storage),
) -> Response:
    """Streams stored document bytes directly, used primarily for local/offline dev storage."""
    try:
        content = storage.download_bytes(key)
        media_type, _ = mimetypes.guess_type(key)
        return Response(
            content=content,
            media_type=media_type or "application/octet-stream",
        )
    except StorageFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
