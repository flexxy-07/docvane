from typing import Any

from fastapi import APIRouter, Response, status

from backend.app.core.config import settings
from backend.app.core.health import check_all_services

router = APIRouter(tags=["Health"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, Any]:
    """
    Liveness probe: returns 200 OK immediately if the service process is alive.
    Used by orchestrators (Kubernetes / Cloud Run) to detect crashes.
    """
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    result = await check_all_services()
    if result["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    else:
        response.status_code = status.HTTP_200_OK

    return result
