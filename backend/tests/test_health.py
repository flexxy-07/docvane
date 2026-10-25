import pytest
from httpx import ASGITransport, AsyncClient
from backend.app.main import app


@pytest.mark.asyncio
async def test_healthz_liveness_probe() -> None:
    """Verifies that /healthz returns 200 OK immediately."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Docvane"


@pytest.mark.asyncio
async def test_readyz_readiness_probe() -> None:
    """Verifies that /readyz connects to PostgreSQL and Redis and returns 200 OK."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["services"]["database"]["status"] == "healthy"
    assert data["services"]["redis"]["status"] == "healthy"
