import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import ReviewStatus


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    field_id: uuid.UUID
    field_name: str | None = None
    field_value: str | None = None
    confidence: float | None = None
    source_page: int | None = None
    bbox: list[float] | None = None
    assigned_to_user_id: uuid.UUID | None = None
    status: ReviewStatus
    corrected_value: str | None = None
    reviewed_at: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewTaskListResponse(BaseModel):
    items: list[ReviewTaskResponse]
    total: int
    skip: int = 0
    limit: int = Field(default=50, ge=1, le=100)


class ReviewTaskResolveRequest(BaseModel):
    action: Literal["approve", "correct"]
    corrected_value: str | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    field_name: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime
