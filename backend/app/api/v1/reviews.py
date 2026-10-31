import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_tenant_id, get_optional_user_id, get_tenant_db
from backend.app.db.models import ReviewStatus
from backend.app.schemas.review import (
    AuditLogResponse,
    ReviewTaskListResponse,
    ReviewTaskResolveRequest,
    ReviewTaskResponse,
)
from backend.app.services.review import (
    ReviewService,
    ReviewServiceError,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
    ReviewTaskValidationError,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


def get_review_service() -> ReviewService:
    return ReviewService()


@router.get(
    "",
    response_model=ReviewTaskListResponse,
    summary="List review tasks for the tenant",
)
async def list_review_tasks(
    document_id: uuid.UUID | None = Query(None, description="Filter by document ID"),
    task_status: ReviewStatus | None = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0, description="Items to skip"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_tenant_db),
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskListResponse:
    """Lists low-confidence extraction review tasks requiring human verification."""
    items, total = await service.list_review_tasks(
        session=db,
        tenant_id=tenant_id,
        document_id=document_id,
        status=task_status,
        skip=skip,
        limit=limit,
    )
    return ReviewTaskListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get(
    "/{task_id}",
    response_model=ReviewTaskResponse,
    summary="Get single review task details",
)
async def get_review_task(
    task_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_tenant_db),
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResponse:
    """Retrieves detailed information for a review task including field data and bounding box."""
    try:
        return await service.get_review_task(
            session=db,
            tenant_id=tenant_id,
            task_id=task_id,
        )
    except ReviewTaskNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{task_id}/claim",
    response_model=ReviewTaskResponse,
    summary="Claim a review task for the current reviewer",
)
async def claim_review_task(
    task_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    user_id: uuid.UUID | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_tenant_db),
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResponse:
    """Assigns the task to the claiming user and sets status to claimed."""
    assigned_user = user_id or uuid.uuid4()
    try:
        return await service.claim_review_task(
            session=db,
            tenant_id=tenant_id,
            task_id=task_id,
            user_id=assigned_user,
        )
    except ReviewTaskNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ReviewTaskConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post(
    "/{task_id}/resolve",
    response_model=ReviewTaskResponse,
    summary="Resolve a review task (approve or correct)",
)
async def resolve_review_task(
    task_id: uuid.UUID,
    payload: ReviewTaskResolveRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    user_id: uuid.UUID | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_tenant_db),
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResponse:
    """Resolves an extracted field review task with approval or correction, and logs audit."""
    reviewer_user = user_id or uuid.uuid4()
    try:
        return await service.resolve_review_task(
            session=db,
            tenant_id=tenant_id,
            task_id=task_id,
            user_id=reviewer_user,
            action=payload.action,
            corrected_value=payload.corrected_value,
        )
    except ReviewTaskNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ReviewTaskConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ReviewTaskValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except ReviewServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/documents/{document_id}/audit-trail",
    response_model=list[AuditLogResponse],
    summary="Get audit trail for a document",
)
async def get_document_audit_trail(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_tenant_db),
    service: ReviewService = Depends(get_review_service),
) -> list[AuditLogResponse]:
    """Retrieves full audit log history of field changes and reviews for a document."""
    return await service.get_audit_trail(
        session=db,
        tenant_id=tenant_id,
        document_id=document_id,
    )
