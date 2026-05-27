from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CompanyCreate, CompanyListResponse, CompanyRead
from app.services import company_service


router = APIRouter()


@router.get("", response_model=CompanyListResponse)
def list_companies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    return CompanyListResponse(
        items=company_service.list_companies(db, skip=skip, limit=limit),
        total=company_service.count_companies(db),
    )


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)) -> CompanyRead:
    return company_service.create_company(db, payload)
