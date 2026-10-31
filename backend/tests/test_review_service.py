import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.db.models import (
    Document,
    DocumentStatus,
    ExtractedFieldModel,
    FieldStatus,
    Invoice,
    ReviewStatus,
    ReviewTask,
)
from backend.app.services.review import (
    ReviewService,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
    ReviewTaskValidationError,
)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def doc_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_extracted_field(tenant_id: uuid.UUID, doc_id: uuid.UUID) -> ExtractedFieldModel:
    field_id = uuid.uuid4()
    return ExtractedFieldModel(
        id=field_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        field_name="total_amount",
        field_value="150.00",
        confidence=0.65,
        source_page=1,
        bbox=[0.1, 0.2, 0.3, 0.4],
        status=FieldStatus.NEEDS_REVIEW,
    )


@pytest.fixture
def mock_review_task(
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    mock_extracted_field: ExtractedFieldModel,
) -> ReviewTask:
    task_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)
    task = ReviewTask(
        id=task_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        field_id=mock_extracted_field.id,
        assigned_to_user_id=None,
        status=ReviewStatus.PENDING,
        corrected_value=None,
        reviewed_at=None,
        created_at=now,
        updated_at=now,
    )
    task.field = mock_extracted_field
    return task


@pytest.mark.asyncio
async def test_list_review_tasks(
    tenant_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    # Mock count query
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1

    # Mock items query
    items_res = MagicMock()
    items_res.scalars.return_value.all.return_value = [mock_review_task]

    session.execute.side_effect = [count_res, items_res]

    service = ReviewService()
    items, total = await service.list_review_tasks(session, tenant_id)

    assert total == 1
    assert len(items) == 1
    assert items[0].id == mock_review_task.id
    assert items[0].field_name == "total_amount"
    assert items[0].confidence == 0.65
    assert items[0].status == ReviewStatus.PENDING


@pytest.mark.asyncio
async def test_get_review_task_found(
    tenant_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = mock_review_task
    session.execute.return_value = exec_res

    service = ReviewService()
    task = await service.get_review_task(session, tenant_id, mock_review_task.id)

    assert task.id == mock_review_task.id
    assert task.field_name == "total_amount"
    assert task.confidence == 0.65


@pytest.mark.asyncio
async def test_get_review_task_not_found(tenant_id: uuid.UUID) -> None:
    session = AsyncMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = None
    session.execute.return_value = exec_res

    service = ReviewService()
    with pytest.raises(ReviewTaskNotFoundError):
        await service.get_review_task(session, tenant_id, uuid.uuid4())


@pytest.mark.asyncio
async def test_claim_review_task_success(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = mock_review_task
    session.execute.return_value = exec_res

    service = ReviewService()
    claimed = await service.claim_review_task(session, tenant_id, mock_review_task.id, user_id)

    assert claimed.status == ReviewStatus.CLAIMED
    assert claimed.assigned_to_user_id == user_id
    assert session.commit.called


@pytest.mark.asyncio
async def test_claim_already_resolved_conflict(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    mock_review_task.status = ReviewStatus.APPROVED
    session = AsyncMock()
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = mock_review_task
    session.execute.return_value = exec_res

    service = ReviewService()
    with pytest.raises(ReviewTaskConflictError):
        await service.claim_review_task(session, tenant_id, mock_review_task.id, user_id)


@pytest.mark.asyncio
async def test_resolve_review_task_approve(
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()

    # 1. Fetch task
    task_res = MagicMock()
    task_res.scalar_one_or_none.return_value = mock_review_task

    # 2. Count remaining pending tasks -> 0
    pending_res = MagicMock()
    pending_res.scalar_one.return_value = 0

    # 3. Fetch doc
    now = datetime.datetime.now(datetime.UTC)
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="invoice.pdf",
        file_type="pdf",
        status=DocumentStatus.NEEDS_REVIEW,
        storage_key="dummy_key",
        file_size_bytes=1000,
        page_count=1,
        created_at=now,
        updated_at=now,
    )
    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = doc

    session.execute.side_effect = [task_res, pending_res, doc_res]

    mock_doc_service = MagicMock()
    mock_doc_service.transition_status = AsyncMock()

    service = ReviewService(document_service=mock_doc_service)
    resolved = await service.resolve_review_task(
        session=session,
        tenant_id=tenant_id,
        task_id=mock_review_task.id,
        user_id=user_id,
        action="approve",
    )

    assert resolved.status == ReviewStatus.APPROVED
    assert mock_review_task.field.status == FieldStatus.AUTO
    assert session.commit.called
    # Check that document lifecycle advanced
    assert mock_doc_service.transition_status.call_count == 2


@pytest.mark.asyncio
async def test_resolve_review_task_correct(
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()

    # 1. Fetch task
    task_res = MagicMock()
    task_res.scalar_one_or_none.return_value = mock_review_task

    # 2. Query Invoice for typed column update
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=doc_id,
        total_amount=150.0,
    )
    inv_res = MagicMock()
    inv_res.scalar_one_or_none.return_value = invoice

    # 3. Count remaining pending tasks -> 0
    pending_res = MagicMock()
    pending_res.scalar_one.return_value = 0

    # 4. Fetch doc
    now = datetime.datetime.now(datetime.UTC)
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="invoice.pdf",
        file_type="pdf",
        status=DocumentStatus.NEEDS_REVIEW,
        storage_key="dummy_key",
        file_size_bytes=1000,
        page_count=1,
        created_at=now,
        updated_at=now,
    )
    doc_res = MagicMock()
    doc_res.scalar_one_or_none.return_value = doc

    session.execute.side_effect = [task_res, inv_res, pending_res, doc_res]

    mock_doc_service = MagicMock()
    mock_doc_service.transition_status = AsyncMock()

    service = ReviewService(document_service=mock_doc_service)
    resolved = await service.resolve_review_task(
        session=session,
        tenant_id=tenant_id,
        task_id=mock_review_task.id,
        user_id=user_id,
        action="correct",
        corrected_value="250.50",
    )

    assert resolved.status == ReviewStatus.CORRECTED
    assert resolved.corrected_value == "250.50"
    assert mock_review_task.field.field_value == "250.50"
    assert mock_review_task.field.status == FieldStatus.CORRECTED
    assert invoice.total_amount == 250.50


@pytest.mark.asyncio
async def test_resolve_correct_without_value_raises(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    mock_review_task: ReviewTask,
) -> None:
    session = AsyncMock()
    task_res = MagicMock()
    task_res.scalar_one_or_none.return_value = mock_review_task
    session.execute.return_value = task_res

    service = ReviewService()
    with pytest.raises(ReviewTaskValidationError):
        await service.resolve_review_task(
            session=session,
            tenant_id=tenant_id,
            task_id=mock_review_task.id,
            user_id=user_id,
            action="correct",
            corrected_value=None,
        )
