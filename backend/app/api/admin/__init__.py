from fastapi import APIRouter, Depends

from app.api.admin.cache import router as cache_router
from app.api.admin.providers import router as providers_router
from app.core.admin_auth import require_admin_auth


router = APIRouter(dependencies=[Depends(require_admin_auth)])
router.include_router(cache_router, prefix="/cache", tags=["admin"])
router.include_router(providers_router, prefix="/providers", tags=["admin"])
