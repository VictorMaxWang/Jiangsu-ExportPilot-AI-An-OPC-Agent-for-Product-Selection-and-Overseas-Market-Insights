from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CompanyCreate, CompanyListResponse, CompanyRead, CompanyUpdate
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


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: int, db: Session = Depends(get_db)) -> CompanyRead:
    return _get_company_or_404(db, company_id)


@router.put("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
) -> CompanyRead:
    company = _get_company_or_404(db, company_id)
    return company_service.update_company(db, company, payload)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)) -> Response:
    company = _get_company_or_404(db, company_id)
    company_service.delete_company(db, company)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_company_or_404(db: Session, company_id: int):
    company = company_service.get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company
