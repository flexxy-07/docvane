
from fastapi import APIRouter

from backend.app.api.v1.documents import router as documents_router

api_v1_router = APIRouter()
api_v1_router.include_router(documents_router)

__all__ = ["api_v1_router"]
