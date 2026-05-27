from fastapi import APIRouter

from app.api.ai import router as ai_router
from app.api.companies import router as companies_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.products import router as products_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(ai_router, prefix="/api/ai", tags=["ai"])
api_router.include_router(companies_router, prefix="/api/companies", tags=["companies"])
api_router.include_router(imports_router, prefix="/api/import", tags=["import"])
api_router.include_router(products_router, prefix="/api/products", tags=["products"])
