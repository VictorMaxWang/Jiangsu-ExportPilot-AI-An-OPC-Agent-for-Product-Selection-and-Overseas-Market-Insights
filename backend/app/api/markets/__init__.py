from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.ai import get_bailian_client
from app.schemas import MarketCompareRequest, MarketCompareResponse, MarketProfileAnalysisResponse
from app.services.ai import BailianClient
from app.services.analysis import MarketProfileAnalysisService
from app.services.data_sources import DataSourceService, get_data_source_service


router = APIRouter()


def get_market_profile_analysis_service(
    data_source_service: DataSourceService = Depends(get_data_source_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> MarketProfileAnalysisService:
    return MarketProfileAnalysisService(data_source_service, ai_client=ai_client)


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
        raise _validation_exception(str(exc)) from exc


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
        raise _validation_exception(str(exc)) from exc


def _validation_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "UNSUPPORTED_DATA_SOURCE_INPUT",
            "message": message,
        },
    )
