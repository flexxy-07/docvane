import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import DocumentStatus


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    filename : str
    file_type: str
    status: DocumentStatus
    storage_key : str
    checksum: str
    file_size_bytes: int
    page_count: int = 0
    is_duplicate: bool = False
    created_at: datetime

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    filename: str
    file_type: str
    doc_type: str | None = None
    status: DocumentStatus
    storage_key: str
    checksum: str | None = None
    file_size_bytes: int
    page_count: int
    error_message: str | None = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    download_url: str | None = None

class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    items: list[DocumentResponse]
    total: int
    skip: int = 0
    limit: int = Field(default=50, ge=1, le=100)

