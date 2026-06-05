from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    AnalysisCountryPresetCatalogResponse,
    MarketCompareRequest,
    MarketCompareResponse,
    MarketProfileAnalysisResponse,
    TargetCountryCatalogResponse,
)
from app.services.ai import BailianClient
from app.services.analysis import MarketProfileAnalysisService
from app.services.data_sources import DataSourceService, get_data_source_service
from app.services.target_market_catalog import TargetMarketCatalogService
from app.utils.redaction import redact_text


router = APIRouter()


def get_market_profile_analysis_service(
    db: Session = Depends(get_db),
    data_source_service: DataSourceService = Depends(get_data_source_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> MarketProfileAnalysisService:
    return MarketProfileAnalysisService(
        data_source_service,
        ai_client=ai_client,
        catalog_service=TargetMarketCatalogService(db),
    )


def get_target_market_catalog_service(db: Session = Depends(get_db)) -> TargetMarketCatalogService:
    return TargetMarketCatalogService(db)


@router.get("/countries", response_model=TargetCountryCatalogResponse)
def list_target_countries(
    region_code: str | None = Query(default=None, min_length=1, max_length=64),
    continent: str | None = Query(default=None, min_length=1, max_length=64),
    include_disabled: bool = Query(default=False),
    analysis_only: bool = Query(default=True),
    service: TargetMarketCatalogService = Depends(get_target_market_catalog_service),
) -> TargetCountryCatalogResponse:
    return service.list_countries(
        region_code=region_code,
        continent=continent,
        include_disabled=include_disabled,
        analysis_only=analysis_only,
    )


@router.get("/presets", response_model=AnalysisCountryPresetCatalogResponse)
def list_country_presets(
    region_code: str | None = Query(default=None, min_length=1, max_length=64),
    default_only: bool = Query(default=False),
    include_disabled: bool = Query(default=False),
    service: TargetMarketCatalogService = Depends(get_target_market_catalog_service),
) -> AnalysisCountryPresetCatalogResponse:
    return service.list_presets(
        region_code=region_code,
        default_only=default_only,
        include_disabled=include_disabled,
    )


@router.get("/{country_code}/profile", response_model=MarketProfileAnalysisResponse)
async def get_country_profile(
    country_code: str,
    product_category: str = Query(..., min_length=1),
    keyword: str | None = Query(default=None, min_length=1),
    hs_code: str | None = Query(default=None, min_length=1, max_length=16),
    service: MarketProfileAnalysisService = Depends(get_market_profile_analysis_service),
) -> MarketProfileAnalysisResponse:
    try:
        return await service.analyze_country(
            country_code,
            product_category,
            keyword=keyword,
            hs_code=hs_code,
        )
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


@router.post("/compare", response_model=MarketCompareResponse)
async def compare_markets(
    request: MarketCompareRequest,
    service: MarketProfileAnalysisService = Depends(get_market_profile_analysis_service),
) -> MarketCompareResponse:
    try:
        return await service.compare_markets(
            request.product_category,
            country_codes=request.country_codes,
            keyword=request.keyword,
            hs_code=request.hs_code,
        )
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


def _validation_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "UNSUPPORTED_DATA_SOURCE_INPUT",
            "message": message,
        },
    )
