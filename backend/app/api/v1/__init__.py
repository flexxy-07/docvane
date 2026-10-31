
from fastapi import APIRouter

from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.reviews import router as reviews_router

api_v1_router = APIRouter()
api_v1_router.include_router(documents_router)
api_v1_router.include_router(reviews_router)

__all__ = ["api_v1_router"]
