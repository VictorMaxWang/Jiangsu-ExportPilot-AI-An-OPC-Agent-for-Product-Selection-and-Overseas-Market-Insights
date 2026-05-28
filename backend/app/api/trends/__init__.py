from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.ai import get_bailian_client
from app.schemas import ContentTrendAnalysisRequest, ContentTrendAnalysisResponse
from app.services.ai import BailianClient
from app.services.analysis import ContentTrendAnalysisService
from app.services.data_sources import DataSourceService, get_data_source_service


router = APIRouter()


def get_content_trend_analysis_service(
    data_source_service: DataSourceService = Depends(get_data_source_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> ContentTrendAnalysisService:
    return ContentTrendAnalysisService(data_source_service, ai_client=ai_client)


@router.post("/content/analyze", response_model=ContentTrendAnalysisResponse)
async def analyze_content_trends(
    request: ContentTrendAnalysisRequest,
    service: ContentTrendAnalysisService = Depends(get_content_trend_analysis_service),
) -> ContentTrendAnalysisResponse:
    try:
        return await service.analyze(request.keyword, request.country)
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
