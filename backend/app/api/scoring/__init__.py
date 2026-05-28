from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import ScoringResultsResponse, ScoringRunRequest, ScoringRunResponse
from app.services.ai import BailianClient
from app.services.data_sources import DataSourceService, get_data_source_service
from app.services.scoring import OpportunityScoringService


router = APIRouter()


def get_opportunity_scoring_service(
    db: Session = Depends(get_db),
    data_source_service: DataSourceService = Depends(get_data_source_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> OpportunityScoringService:
    return OpportunityScoringService(db, data_source_service, ai_client=ai_client)


@router.post("/run", response_model=ScoringRunResponse)
async def run_scoring(
    request: ScoringRunRequest,
    service: OpportunityScoringService = Depends(get_opportunity_scoring_service),
) -> ScoringRunResponse:
    try:
        return await service.run(request)
    except ValueError as exc:
        message = str(exc)
        if message == "Company not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "UNSUPPORTED_SCORING_INPUT", "message": message},
        ) from exc


@router.get("/results/{analysis_id}", response_model=ScoringResultsResponse)
def get_scoring_results(
    analysis_id: int,
    service: OpportunityScoringService = Depends(get_opportunity_scoring_service),
) -> ScoringResultsResponse:
    result = service.results(analysis_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return result
