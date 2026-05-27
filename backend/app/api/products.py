from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProductCreate, ProductListResponse, ProductRead
from app.services import product_service


router = APIRouter()


@router.get("", response_model=ProductListResponse)
def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    company_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    return ProductListResponse(
        items=product_service.list_products(
            db,
            skip=skip,
            limit=limit,
            company_id=company_id,
        ),
        total=product_service.count_products(db, company_id=company_id),
    )


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductRead:
    if not product_service.company_exists(db, payload.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return product_service.create_product(db, payload)
