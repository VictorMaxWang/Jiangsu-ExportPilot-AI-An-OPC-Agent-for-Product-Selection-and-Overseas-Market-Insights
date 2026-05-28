from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.analysis import router as analysis_router
from app.api.ai import router as ai_router
from app.api.companies import router as companies_router
from app.api.data import router as data_router
from app.api.data_sources import router as data_sources_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.marketing import router as marketing_router
from app.api.markets import router as markets_router
from app.api.products import router as products_router
from app.api.reports import router as reports_router
from app.api.scoring import router as scoring_router
from app.api.trends import router as trends_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(admin_router, prefix="/api/admin", tags=["admin"])
api_router.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
api_router.include_router(ai_router, prefix="/api/ai", tags=["ai"])
api_router.include_router(companies_router, prefix="/api/companies", tags=["companies"])
api_router.include_router(data_router, prefix="/api/data", tags=["data"])
api_router.include_router(data_sources_router, prefix="/api/data-sources", tags=["data-sources"])
api_router.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
api_router.include_router(imports_router, prefix="/api/import", tags=["import"])
api_router.include_router(marketing_router, prefix="/api/marketing", tags=["marketing"])
api_router.include_router(markets_router, prefix="/api/markets", tags=["markets"])
api_router.include_router(products_router, prefix="/api/products", tags=["products"])
api_router.include_router(reports_router, prefix="/api/reports", tags=["reports"])
api_router.include_router(scoring_router, prefix="/api/scoring", tags=["scoring"])
api_router.include_router(trends_router, prefix="/api/trends", tags=["trends"])
