import datetime
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_tenant_db
from backend.app.api.v1.reviews import get_review_service
from backend.app.db.models import ReviewStatus
from backend.app.main import app
from backend.app.schemas.review import (
    AuditLogResponse,
    ReviewTaskResponse,
)
from backend.app.services.review import (
    ReviewService,
    ReviewTaskConflictError,
    ReviewTaskNotFoundError,
)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def task_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def doc_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_task_response(
    task_id: uuid.UUID,
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
) -> ReviewTaskResponse:
    now = datetime.datetime.now(datetime.UTC)
    return ReviewTaskResponse(
        id=task_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        field_id=uuid.uuid4(),
        field_name="total_amount",
        field_value="100.00",
        confidence=0.72,
        source_page=1,
        bbox=[0.1, 0.2, 0.3, 0.4],
        assigned_to_user_id=None,
        status=ReviewStatus.PENDING,
        corrected_value=None,
        reviewed_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_review_service(sample_task_response: ReviewTaskResponse) -> MagicMock:
    service = MagicMock(spec=ReviewService)
    service.list_review_tasks = AsyncMock(return_value=([sample_task_response], 1))
    service.get_review_task = AsyncMock(return_value=sample_task_response)
    service.claim_review_task = AsyncMock(
        return_value=sample_task_response.model_copy(
            update={"status": ReviewStatus.CLAIMED, "assigned_to_user_id": uuid.uuid4()}
        )
    )
    service.resolve_review_task = AsyncMock(
        return_value=sample_task_response.model_copy(
            update={"status": ReviewStatus.APPROVED}
        )
    )
    service.get_audit_trail = AsyncMock(return_value=[])
    return service


@pytest.fixture
async def async_client(
    mock_review_service: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_review_service] = lambda: mock_review_service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_review_tasks_api(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    headers = {"X-Tenant-ID": str(tenant_id)}
    response = await async_client.get("/api/v1/reviews", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["field_name"] == "total_amount"
    assert data["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_review_task_api_success(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    headers = {"X-Tenant-ID": str(tenant_id)}
    response = await async_client.get(f"/api/v1/reviews/{task_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task_id)
    assert data["field_name"] == "total_amount"


@pytest.mark.asyncio
async def test_get_review_task_api_not_found(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    mock_review_service.get_review_task.side_effect = ReviewTaskNotFoundError("Task not found")
    headers = {"X-Tenant-ID": str(tenant_id)}
    response = await async_client.get(f"/api/v1/reviews/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_claim_review_task_api(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    reviewer_id = uuid.uuid4()
    headers = {"X-Tenant-ID": str(tenant_id), "X-User-ID": str(reviewer_id)}
    response = await async_client.post(f"/api/v1/reviews/{task_id}/claim", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "claimed"
    assert mock_review_service.claim_review_task.called


@pytest.mark.asyncio
async def test_claim_review_task_conflict(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    mock_review_service.claim_review_task.side_effect = ReviewTaskConflictError("Already resolved")
    headers = {"X-Tenant-ID": str(tenant_id)}
    response = await async_client.post(f"/api/v1/reviews/{task_id}/claim", headers=headers)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_resolve_review_task_api(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    headers = {"X-Tenant-ID": str(tenant_id)}
    payload = {"action": "approve"}
    response = await async_client.post(
        f"/api/v1/reviews/{task_id}/resolve",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert mock_review_service.resolve_review_task.called


@pytest.mark.asyncio
async def test_get_audit_trail_api(
    async_client: AsyncClient,
    tenant_id: uuid.UUID,
    doc_id: uuid.UUID,
    mock_review_service: MagicMock,
) -> None:
    now = datetime.datetime.now(datetime.UTC)
    mock_review_service.get_audit_trail.return_value = [
        AuditLogResponse(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            document_id=doc_id,
            user_id=uuid.uuid4(),
            action="field_corrected",
            field_name="total_amount",
            old_value="100.00",
            new_value="120.00",
            created_at=now,
        )
    ]
    headers = {"X-Tenant-ID": str(tenant_id)}
    response = await async_client.get(
        f"/api/v1/reviews/documents/{doc_id}/audit-trail",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["action"] == "field_corrected"
    assert data[0]["new_value"] == "120.00"
