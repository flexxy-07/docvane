import datetime
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import get_storage, get_tenant_db
from backend.app.db.models import Document, DocumentStatus
from backend.app.main import app
from backend.app.services.document import (
    DocumentNotFoundError,
    DocumentService,
    DocumentValidationError,
    get_document_service,
)
from backend.app.services.storage import StorageService


@pytest.fixture
def mock_storage() -> MagicMock:
    storage = MagicMock(spec=StorageService)
    storage.generate_presigned_url.return_value = "https://mock-storage.com/signed-url"
    storage.download_bytes.return_value = b"Raw file stream content"
    return storage


@pytest.fixture
def mock_document_service() -> MagicMock:
    service = MagicMock(spec=DocumentService)
    service.get_download_url.return_value = "https://mock-storage.com/signed-url"
    return service


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(tenant_id: uuid.UUID) -> Document:
    doc_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)
    return Document(
        id=doc_id,
        tenant_id=tenant_id,
        filename="contract.pdf",
        file_type="pdf",
        doc_type="contract",
        status=DocumentStatus.UPLOADED,
        storage_key=f"{tenant_id}/{doc_id}/contract.pdf",
        checksum="1234567890abcdef" * 4,
        file_size_bytes=4096,
        page_count=2,
        error_message=None,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_upload_missing_tenant_header() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", b"%PDF-test-bytes", "application/pdf")},
        )
    assert response.status_code == 400
    assert "Missing required header 'X-Tenant-ID'" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_tenant_uuid() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/upload",
            headers={"X-Tenant-ID": "invalid-uuid"},
            files={"file": ("test.pdf", b"%PDF-test-bytes", "application/pdf")},
        )
    assert response.status_code == 400
    assert "must be a valid UUID format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_document_success(
    tenant_id: uuid.UUID,
    sample_document: Document,
    mock_document_service: MagicMock,
    mock_storage: MagicMock,
) -> None:
    mock_document_service.upload_document = AsyncMock(
        return_value=(sample_document, False)
    )

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    app.dependency_overrides[get_storage] = lambda: mock_storage

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/upload",
                headers={"X-Tenant-ID": str(tenant_id)},
                files={"file": ("contract.pdf", b"%PDF-content", "application/pdf")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(sample_document.id)
        assert data["filename"] == "contract.pdf"
        assert data["status"] == "uploaded"
        assert data["is_duplicate"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_document_validation_error(
    tenant_id: uuid.UUID,
    mock_document_service: MagicMock,
) -> None:
    mock_document_service.upload_document = AsyncMock(
        side_effect=DocumentValidationError("Unsupported file extension '.exe'")
    )

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/documents/upload",
                headers={"X-Tenant-ID": str(tenant_id)},
                files={"file": ("bad.exe", b"binary", "application/octet-stream")},
            )

        assert response.status_code == 400
        assert "Unsupported file extension '.exe'" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_documents(
    tenant_id: uuid.UUID,
    sample_document: Document,
    mock_document_service: MagicMock,
) -> None:
    mock_document_service.list_documents = AsyncMock(
        return_value=([sample_document], 1)
    )

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/documents?skip=0&limit=10",
                headers={"X-Tenant-ID": str(tenant_id)},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(sample_document.id)
        assert data["items"][0]["download_url"] == "https://mock-storage.com/signed-url"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_document_by_id(
    tenant_id: uuid.UUID,
    sample_document: Document,
    mock_document_service: MagicMock,
) -> None:
    mock_document_service.get_document = AsyncMock(return_value=sample_document)

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{sample_document.id}",
                headers={"X-Tenant-ID": str(tenant_id)},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_document.id)
        assert data["filename"] == "contract.pdf"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_document_not_found(
    tenant_id: uuid.UUID,
    mock_document_service: MagicMock,
) -> None:
    non_existent_id = uuid.uuid4()
    mock_document_service.get_document = AsyncMock(
        side_effect=DocumentNotFoundError(f"Document {non_existent_id} not found")
    )

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/documents/{non_existent_id}",
                headers={"X-Tenant-ID": str(tenant_id)},
            )

        assert response.status_code == 404
        assert f"Document {non_existent_id} not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document(
    tenant_id: uuid.UUID,
    mock_document_service: MagicMock,
) -> None:
    doc_id = uuid.uuid4()
    mock_document_service.delete_document = AsyncMock()

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_document_service] = lambda: mock_document_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/documents/{doc_id}",
                headers={"X-Tenant-ID": str(tenant_id)},
            )

        assert response.status_code == 204
        mock_document_service.delete_document.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_raw_document(
    mock_storage: MagicMock,
) -> None:
    app.dependency_overrides[get_storage] = lambda: mock_storage

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/raw/tenant-1/doc-1/test.pdf")

        assert response.status_code == 200
        assert response.content == b"Raw file stream content"
        assert response.headers.get("content-type") == "application/pdf"
    finally:
        app.dependency_overrides.clear()
