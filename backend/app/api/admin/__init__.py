from fastapi import APIRouter

from app.api.admin.providers import router as providers_router


router = APIRouter()
router.include_router(providers_router, prefix="/providers", tags=["admin"])
