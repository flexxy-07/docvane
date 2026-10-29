import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import AsyncSessionLocal
from backend.app.services.storage import StorageService, get_storage_service


def get_current_tenant_id(request: Request) -> uuid.UUID:
    """Extract and validate tenant ID from request headers."""

    tenant_header = request.headers.get("X-Tenant-ID")
    if not tenant_header:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Missing required header 'X-Tenant-ID'"
      )

    try:
        return uuid.UUID(tenant_header)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 'X-Tenant-ID' header: must be a valid UUID format",
        ) from None

async def get_tenant_db(
  tenant_id: uuid.UUID = Depends(get_current_tenant_id),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an AsyncSession bound to the current tenant for Row-Level Security (RLS).
    Executes PostgreSQL set_config to set 'app.current_tenant_id'.
    """
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
        finally:
            await session.close()

def get_storage() -> StorageService:
  """ Dependency provider for the storage service """
  return get_storage_service()
