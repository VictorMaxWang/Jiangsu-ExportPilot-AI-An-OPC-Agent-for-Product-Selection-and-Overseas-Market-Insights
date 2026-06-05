from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    ProductDraftConfirmRequest,
    ProductDraftListResponse,
    ProductDraftRead,
    ProductDraftRejectRequest,
    ProductDraftUpdateRequest,
    ProductImportJobDetailResponse,
    ProductRead,
    ProductScreenshotIntakeResponse,
    ProductScreenshotsIntakeResponse,
    ProductUrlIntakeRequest,
    ProductUrlIntakeResponse,
)
from app.services.ai import BailianClient
from app.services.product_intake import (
    ProductIntakeRequestError,
    analyze_screenshot_upload,
    analyze_screenshot_uploads,
    analyze_url_intake,
    confirm_product_draft,
    get_draft_detail,
    get_job_detail,
    list_product_drafts,
    reject_product_draft,
    update_product_draft,
)


router = APIRouter()


@router.post(
    "/screenshot",
    response_model=ProductScreenshotIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_screenshot(
    company_id: int = Form(...),
    file: UploadFile = File(...),
    source_platform: str | None = Form(default=None),
    db: Session = Depends(get_db),
    client: BailianClient = Depends(get_bailian_client),
) -> ProductScreenshotIntakeResponse:
    try:
        return await analyze_screenshot_upload(
            db,
            company_id=company_id,
            upload=file,
            source_platform=source_platform,
            client=client,
        )
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post(
    "/screenshots",
    response_model=ProductScreenshotsIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_screenshots(
    company_id: int = Form(...),
    source_platform: str | None = Form(default=None),
    files_bracket: list[UploadFile] | None = File(default=None, alias="files[]"),
    files_plain: list[UploadFile] | None = File(default=None, alias="files"),
    image_roles_bracket: list[str] | None = Form(default=None, alias="image_roles[]"),
    image_roles_plain: list[str] | None = Form(default=None, alias="image_roles"),
    db: Session = Depends(get_db),
    client: BailianClient = Depends(get_bailian_client),
) -> ProductScreenshotsIntakeResponse:
    uploads = [*(files_bracket or []), *(files_plain or [])]
    image_roles = [*(image_roles_bracket or []), *(image_roles_plain or [])]
    try:
        return await analyze_screenshot_uploads(
            db,
            company_id=company_id,
            uploads=uploads,
            source_platform=source_platform,
            image_roles=image_roles,
            client=client,
        )
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post(
    "/url",
    response_model=ProductUrlIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_product_url(
    payload: ProductUrlIntakeRequest,
    db: Session = Depends(get_db),
    client: BailianClient = Depends(get_bailian_client),
) -> ProductUrlIntakeResponse:
    try:
        return await analyze_url_intake(
            db,
            company_id=payload.company_id,
            url=payload.url,
            client=client,
        )
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.get("/jobs/{job_id}", response_model=ProductImportJobDetailResponse)
def get_product_intake_job(
    job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> ProductImportJobDetailResponse:
    result = get_job_detail(db, job_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product import job not found")
    return result


@router.get("/drafts", response_model=ProductDraftListResponse)
def list_product_intake_drafts(
    company_id: int | None = Query(default=None, gt=0),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    source_platform: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProductDraftListResponse:
    try:
        return list_product_drafts(
            db,
            company_id=company_id,
            status=status_filter,
            source_platform=source_platform,
            limit=limit,
            offset=offset,
        )
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.get("/drafts/{draft_id}", response_model=ProductDraftRead)
def get_product_draft(
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    result = get_draft_detail(db, draft_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product draft not found")
    return result


@router.put("/drafts/{draft_id}", response_model=ProductDraftRead)
def update_product_intake_draft(
    payload: ProductDraftUpdateRequest,
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    try:
        return update_product_draft(db, draft_id, payload)
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post("/drafts/{draft_id}/confirm", response_model=ProductRead)
def confirm_product_intake_draft(
    payload: ProductDraftConfirmRequest,
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> ProductRead:
    try:
        return confirm_product_draft(db, draft_id, payload)
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post("/drafts/{draft_id}/reject", response_model=ProductDraftRead)
def reject_product_intake_draft(
    payload: ProductDraftRejectRequest,
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    try:
        return reject_product_draft(db, draft_id, payload)
    except ProductIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


def _intake_http_exception(exc: ProductIntakeRequestError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )
