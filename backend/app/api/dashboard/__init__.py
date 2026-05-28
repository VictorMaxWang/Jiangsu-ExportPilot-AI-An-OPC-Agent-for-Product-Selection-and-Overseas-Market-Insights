from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DashboardResponse
from app.services.dashboard_service import DashboardService


router = APIRouter()


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/{analysis_id}", response_model=DashboardResponse)
def get_dashboard(
    analysis_id: int,
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    response = service.get_dashboard(analysis_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return response
