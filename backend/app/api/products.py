from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    CsvImportRequest,
    CsvImportResult,
    ProductCreate,
    ProductKeywordGenerationRequest,
    ProductKeywordGenerationResponse,
    ProductKeywordsRequest,
    ProductListResponse,
    ProductRead,
    ProductUpdate,
)
from app.services import product_service
from app.services.ai import (
    AiStructuredOutputError,
    BailianAuthenticationError,
    BailianClient,
    BailianConfigurationError,
    BailianError,
    BailianRateLimitError,
    BailianResponseError,
    BailianTimeoutError,
    BailianUpstreamError,
    generate_product_keywords,
)
from app.services.importers import csv_importer


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


@router.post("/import", response_model=CsvImportResult)
async def import_products(
    request: Request,
    db: Session = Depends(get_db),
) -> CsvImportResult:
    import_request, upload_bytes, upload_name = await _parse_import_request(request)
    if upload_bytes is None:
        return _run_product_import(db, import_request)

    safe_name = Path(upload_name or "product_upload.csv").name or "product_upload.csv"
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        (temp_dir / safe_name).write_bytes(upload_bytes)
        return _run_product_import(db, import_request, file_name=safe_name, seed_dir=temp_dir)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    return _get_product_or_404(db, product_id)


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
) -> ProductRead:
    product = _get_product_or_404(db, product_id)
    if payload.company_id is not None and not product_service.company_exists(db, payload.company_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return product_service.update_product(db, product, payload)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Response:
    product = _get_product_or_404(db, product_id)
    product_service.delete_product(db, product)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{product_id}/generate-keywords", response_model=ProductKeywordGenerationResponse)
async def generate_keywords_for_product(
    product_id: int,
    payload: ProductKeywordGenerationRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    client: BailianClient = Depends(get_bailian_client),
) -> ProductKeywordGenerationResponse:
    request_payload = payload or ProductKeywordGenerationRequest()
    product = _get_product_or_404(db, product_id)
    keyword_payload = _product_to_keyword_request(product, request_payload)
    try:
        result = await generate_product_keywords(keyword_payload, client)
    except BailianError as exc:
        raise _to_ai_http_exception(exc) from exc
    except AiStructuredOutputError as exc:
        raise _structured_output_exception(exc.code, exc.message, errors=exc.errors) from exc

    saved_count = 0
    if request_payload.persist:
        saved_count = product_service.persist_generated_keywords(
            db,
            product,
            result,
            target_country=request_payload.target_country,
        )
    return ProductKeywordGenerationResponse(
        **result.model_dump(),
        saved_keywords_count=saved_count,
    )


def _get_product_or_404(db: Session, product_id: int):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def _parse_import_request(request: Request) -> tuple[CsvImportRequest, bytes | None, str | None]:
    content_type = request.headers.get("content-type", "").split(";")[0].lower()
    if content_type == "multipart/form-data":
        form = await request.form()
        upload = form.get("file")
        if upload is not None and not isinstance(upload, StarletteUploadFile):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="file must be a CSV upload")
        payload = {
            "mode": _optional_form_text(form.get("mode")) or "insert",
            "company_id": _optional_form_text(form.get("company_id")),
            "file_name": None,
        }
        import_request = _validate_import_payload(payload)
        if upload is None:
            return import_request, None, None
        return import_request, await upload.read(), upload.filename

    body = await request.body()
    if not body:
        return CsvImportRequest(), None, None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request body must be valid JSON") from exc
    return _validate_import_payload(payload), None, None


def _optional_form_text(value: Any) -> str | None:
    if value is None or isinstance(value, StarletteUploadFile):
        return None
    text = str(value).strip()
    return text or None


def _validate_import_payload(payload: Any) -> CsvImportRequest:
    try:
        return CsvImportRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc


def _run_product_import(
    db: Session,
    request: CsvImportRequest,
    *,
    file_name: str | None = None,
    seed_dir: Path | None = None,
) -> CsvImportResult:
    try:
        return csv_importer.import_products(
            db,
            file_name=file_name or request.file_name,
            mode=request.mode,
            company_id=request.company_id,
            seed_dir=seed_dir,
        )
    except csv_importer.CsvImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.result.model_dump(mode="json")) from exc
    except csv_importer.CsvImportRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _product_to_keyword_request(
    product,
    payload: ProductKeywordGenerationRequest,
) -> ProductKeywordsRequest:
    return ProductKeywordsRequest(
        product_name_cn=product.product_name_cn,
        product_name_en=product.product_name_en,
        category=product.category,
        material=product.material,
        certification=product.certification,
        cost_price_cny=_decimal_to_str(product.cost_price_cny),
        weight_kg=_decimal_to_str(product.weight_kg),
        package_size=product.package_size,
        moq=product.moq,
        description=product.description,
        target_country=payload.target_country,
        target_platforms=payload.target_platforms,
    )


def _decimal_to_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _to_ai_http_exception(exc: BailianError) -> HTTPException:
    if isinstance(exc, BailianConfigurationError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, BailianTimeoutError):
        http_status = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, BailianRateLimitError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, BailianAuthenticationError):
        http_status = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, (BailianUpstreamError, BailianResponseError)):
        http_status = status.HTTP_502_BAD_GATEWAY
    else:
        http_status = status.HTTP_502_BAD_GATEWAY

    return HTTPException(
        status_code=http_status,
        detail={
            "code": exc.code,
            "message": str(exc),
            "provider": "bailian",
        },
    )


def _structured_output_exception(
    code: str,
    message: str,
    *,
    errors: list[dict[str, object]] | None = None,
) -> HTTPException:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
        "provider": "bailian",
    }
    if errors is not None:
        detail["errors"] = errors
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
