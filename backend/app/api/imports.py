from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CsvImportRequest, CsvImportResult
from app.services.importers import csv_importer


router = APIRouter()


@router.post("/products", response_model=CsvImportResult)
def import_products(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(
        csv_importer.import_products,
        db,
        request,
        company_id=request.company_id,
    )


@router.post("/competitors", response_model=CsvImportResult)
def import_competitors(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_competitors, db, request)


@router.post("/market-profiles", response_model=CsvImportResult)
def import_market_profiles(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_market_profiles, db, request)


@router.post("/target-countries", response_model=CsvImportResult)
def import_target_countries(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_target_countries, db, request)


@router.post("/analysis-country-presets", response_model=CsvImportResult)
def import_analysis_country_presets(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_analysis_country_presets, db, request)


@router.post("/trade-samples", response_model=CsvImportResult)
def import_trade_samples(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_trade_samples, db, request)


@router.post("/content-trends", response_model=CsvImportResult)
def import_content_trends(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_content_trends, db, request)


@router.post("/user-discussions", response_model=CsvImportResult)
def import_user_discussions(
    payload: CsvImportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CsvImportResult:
    request = payload or CsvImportRequest()
    return _run_import(csv_importer.import_user_discussions, db, request)


def _run_import(import_func, db: Session, request: CsvImportRequest, **kwargs) -> CsvImportResult:
    try:
        return import_func(
            db,
            file_name=request.file_name,
            mode=request.mode,
            **kwargs,
        )
    except csv_importer.CsvImportValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.result.model_dump(mode="json")) from exc
    except csv_importer.CsvImportRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
