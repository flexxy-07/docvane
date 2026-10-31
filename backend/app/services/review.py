import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import (
    AuditLog,
    Contract,
    Document,
    DocumentStatus,
    FieldStatus,
    Invoice,
    ReviewStatus,
    ReviewTask,
)
from backend.app.schemas.review import AuditLogResponse, ReviewTaskResponse
from backend.app.services.document import DocumentService

logger = logging.getLogger(__name__)


class ReviewServiceError(Exception):
    """Base exception for review service errors."""

    pass


class ReviewTaskNotFoundError(ReviewServiceError):
    """Raised when a requested review task does not exist."""

    pass


class ReviewTaskValidationError(ReviewServiceError):
    """Raised when a review task operation violates validation rules."""

    pass


class ReviewTaskConflictError(ReviewServiceError):
    """Raised when an operation conflicts with the current task state."""

    pass


def _to_response(task: ReviewTask) -> ReviewTaskResponse:
    field = task.field
    return ReviewTaskResponse(
        id=task.id,
        tenant_id=task.tenant_id,
        document_id=task.document_id,
        field_id=task.field_id,
        field_name=field.field_name if field else None,
        field_value=field.field_value if field else None,
        confidence=field.confidence if field else None,
        source_page=field.source_page if field else None,
        bbox=field.bbox if field else None,
        assigned_to_user_id=task.assigned_to_user_id,
        status=task.status,
        corrected_value=task.corrected_value,
        reviewed_at=task.reviewed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


class ReviewService:
    """Service handling human review workflow, audits, and document advancement."""

    def __init__(self, document_service: DocumentService | None = None) -> None:
        self.doc_service = document_service or DocumentService()

    async def list_review_tasks(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
        status: ReviewStatus | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ReviewTaskResponse], int]:
        """Lists review tasks for a tenant with optional filtering and pagination."""
        base_filters = [ReviewTask.tenant_id == tenant_id]
        if document_id:
            base_filters.append(ReviewTask.document_id == document_id)
        if status:
            base_filters.append(ReviewTask.status == status)
        if assigned_to_user_id:
            base_filters.append(ReviewTask.assigned_to_user_id == assigned_to_user_id)

        count_stmt = select(func.count()).select_from(ReviewTask).where(*base_filters)
        total = (await session.execute(count_stmt)).scalar_one()

        items_stmt = (
            select(ReviewTask)
            .options(selectinload(ReviewTask.field))
            .where(*base_filters)
            .order_by(ReviewTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        tasks = (await session.execute(items_stmt)).scalars().all()
        return [_to_response(t) for t in tasks], total

    async def get_review_task(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> ReviewTaskResponse:
        """Retrieves a single review task by ID."""
        stmt = (
            select(ReviewTask)
            .options(selectinload(ReviewTask.field))
            .where(ReviewTask.id == task_id, ReviewTask.tenant_id == tenant_id)
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            raise ReviewTaskNotFoundError(f"Review task '{task_id}' not found.")
        return _to_response(task)

    async def claim_review_task(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ReviewTaskResponse:
        """Claims a pending review task for the given user."""
        stmt = (
            select(ReviewTask)
            .options(selectinload(ReviewTask.field))
            .where(ReviewTask.id == task_id, ReviewTask.tenant_id == tenant_id)
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            raise ReviewTaskNotFoundError(f"Review task '{task_id}' not found.")

        if task.status in {ReviewStatus.APPROVED, ReviewStatus.CORRECTED}:
            raise ReviewTaskConflictError(
                f"Cannot claim review task in '{task.status.value}' status."
            )

        task.assigned_to_user_id = user_id
        task.status = ReviewStatus.CLAIMED
        await session.commit()
        await session.refresh(task)
        return _to_response(task)

    async def resolve_review_task(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        corrected_value: str | None = None,
    ) -> ReviewTaskResponse:
        """Resolves a review task by approving or correcting an extracted field."""
        stmt = (
            select(ReviewTask)
            .options(selectinload(ReviewTask.field))
            .where(ReviewTask.id == task_id, ReviewTask.tenant_id == tenant_id)
        )
        task = (await session.execute(stmt)).scalar_one_or_none()
        if not task:
            raise ReviewTaskNotFoundError(f"Review task '{task_id}' not found.")

        if task.status in {ReviewStatus.APPROVED, ReviewStatus.CORRECTED}:
            raise ReviewTaskConflictError(
                f"Review task '{task_id}' is already resolved with status '{task.status.value}'."
            )

        field = task.field
        old_val = field.field_value if field else None
        now_iso = datetime.now(UTC).isoformat()

        if action == "correct":
            if corrected_value is None or not str(corrected_value).strip():
                raise ReviewTaskValidationError(
                    "A non-empty 'corrected_value' is required when correcting a field."
                )

            clean_val = str(corrected_value).strip()

            # Record audit log
            audit_log = AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=task.document_id,
                user_id=user_id,
                action="field_corrected",
                field_name=field.field_name if field else None,
                old_value=old_val,
                new_value=clean_val,
            )
            session.add(audit_log)

            # Update ExtractedFieldModel
            if field:
                field.field_value = clean_val
                field.status = FieldStatus.CORRECTED

            # Update task
            task.status = ReviewStatus.CORRECTED
            task.corrected_value = clean_val
            task.assigned_to_user_id = user_id
            task.reviewed_at = now_iso

            # Update corresponding typed table row if present
            await self._update_typed_table_field(
                session=session,
                tenant_id=tenant_id,
                document_id=task.document_id,
                field_name=field.field_name if field else None,
                new_value=clean_val,
            )

        elif action == "approve":
            audit_log = AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=task.document_id,
                user_id=user_id,
                action="field_approved",
                field_name=field.field_name if field else None,
                old_value=old_val,
                new_value=old_val,
            )
            session.add(audit_log)

            if field:
                field.status = FieldStatus.AUTO

            task.status = ReviewStatus.APPROVED
            task.assigned_to_user_id = user_id
            task.reviewed_at = now_iso
        else:
            raise ReviewTaskValidationError(
                f"Invalid action '{action}'. Must be 'approve' or 'correct'."
            )

        await session.commit()
        await session.refresh(task)

        # Check if all review tasks for this document are now resolved
        await self._check_and_advance_document(session, tenant_id, task.document_id)

        return _to_response(task)

    async def get_audit_trail(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> list[AuditLogResponse]:
        """Retrieves audit trail entries for a given document."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.document_id == document_id)
            .order_by(AuditLog.created_at.desc())
        )
        logs = (await session.execute(stmt)).scalars().all()
        return [
            AuditLogResponse(
                id=log.id,
                tenant_id=log.tenant_id,
                document_id=log.document_id,
                user_id=log.user_id,
                action=log.action,
                field_name=log.field_name,
                old_value=log.old_value,
                new_value=log.new_value,
                created_at=log.created_at,
            )
            for log in logs
        ]

    async def _update_typed_table_field(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
        field_name: str | None,
        new_value: str,
    ) -> None:
        """Propagates corrected values to Invoice or Contract tables."""
        if not field_name:
            return

        # Check for Invoice
        inv_stmt = select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.document_id == document_id,
        )
        invoice = (await session.execute(inv_stmt)).scalar_one_or_none()
        if invoice and hasattr(invoice, field_name):
            if field_name in {"subtotal", "tax_amount", "total_amount"}:
                try:
                    num_val = float(new_value.replace("$", "").replace(",", "").strip())
                    setattr(invoice, field_name, num_val)
                except ValueError:
                    logger.warning("Could not convert corrected value '%s' to float", new_value)
            else:
                setattr(invoice, field_name, new_value)
            return

        # Check for Contract
        ctr_stmt = select(Contract).where(
            Contract.tenant_id == tenant_id,
            Contract.document_id == document_id,
        )
        contract = (await session.execute(ctr_stmt)).scalar_one_or_none()
        if contract and hasattr(contract, field_name):
            setattr(contract, field_name, new_value)

    async def _check_and_advance_document(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        """Transitions document from NEEDS_REVIEW -> REVIEWED -> INDEXING if all tasks resolved."""
        pending_stmt = select(func.count()).select_from(ReviewTask).where(
            ReviewTask.tenant_id == tenant_id,
            ReviewTask.document_id == document_id,
            ReviewTask.status.in_([ReviewStatus.PENDING, ReviewStatus.CLAIMED]),
        )
        remaining = (await session.execute(pending_stmt)).scalar_one()
        if remaining > 0:
            return

        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
        doc = (await session.execute(doc_stmt)).scalar_one_or_none()
        if doc and doc.status == DocumentStatus.NEEDS_REVIEW:
            logger.info("All review tasks resolved for doc %s, advancing status", document_id)
            await self.doc_service.transition_status(
                session, tenant_id, document_id, DocumentStatus.REVIEWED
            )
            await self.doc_service.transition_status(
                session, tenant_id, document_id, DocumentStatus.INDEXING
            )
            try:
                from backend.app.workers.tasks import index_document

                index_document.delay(str(document_id), str(tenant_id))
            except Exception as exc:
                logger.warning("Could not dispatch index_document task: %s", str(exc))

