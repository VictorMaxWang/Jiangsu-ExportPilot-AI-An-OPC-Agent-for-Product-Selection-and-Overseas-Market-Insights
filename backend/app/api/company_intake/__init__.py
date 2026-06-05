from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    CompanyDraftConfirmRequest,
    CompanyDraftListResponse,
    CompanyDraftRead,
    CompanyDraftRejectRequest,
    CompanyDraftUpdateRequest,
    CompanyImportJobDetailResponse,
    CompanyPhotoIntakeResponse,
    CompanyRead,
)
from app.services.ai import BailianClient
from app.services.company_intake import (
    CompanyIntakeRequestError,
    analyze_company_photo_uploads,
    confirm_company_draft,
    get_draft_detail,
    get_job_detail,
    list_company_drafts,
    reject_company_draft,
    update_company_draft,
)


router = APIRouter()


@router.post(
    "/photo",
    response_model=CompanyPhotoIntakeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_company_photo(
    source_platform: str | None = Form(default=None),
    files_bracket: list[UploadFile] | None = File(default=None, alias="files[]"),
    files_plain: list[UploadFile] | None = File(default=None, alias="files"),
    image_roles_bracket: list[str] | None = Form(default=None, alias="image_roles[]"),
    image_roles_plain: list[str] | None = Form(default=None, alias="image_roles"),
    db: Session = Depends(get_db),
    client: BailianClient = Depends(get_bailian_client),
) -> CompanyPhotoIntakeResponse:
    uploads = [*(files_bracket or []), *(files_plain or [])]
    image_roles = [*(image_roles_bracket or []), *(image_roles_plain or [])]
    try:
        return await analyze_company_photo_uploads(
            db,
            uploads=uploads,
            source_platform=source_platform,
            image_roles=image_roles,
            client=client,
        )
    except CompanyIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.get("/jobs/{job_id}", response_model=CompanyImportJobDetailResponse)
def get_company_intake_job(
    job_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> CompanyImportJobDetailResponse:
    result = get_job_detail(db, job_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company import job not found")
    return result


@router.get("/drafts", response_model=CompanyDraftListResponse)
def list_company_intake_drafts(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    source_platform: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CompanyDraftListResponse:
    try:
        return list_company_drafts(
            db,
            status=status_filter,
            source_platform=source_platform,
            limit=limit,
            offset=offset,
        )
    except CompanyIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.get("/drafts/{draft_id}", response_model=CompanyDraftRead)
def get_company_draft(
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> CompanyDraftRead:
    result = get_draft_detail(db, draft_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company draft not found")
    return result


@router.put("/drafts/{draft_id}", response_model=CompanyDraftRead)
def update_company_intake_draft(
    payload: CompanyDraftUpdateRequest,
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> CompanyDraftRead:
    try:
        return update_company_draft(db, draft_id, payload)
    except CompanyIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post("/drafts/{draft_id}/confirm", response_model=CompanyRead)
def confirm_company_intake_draft(
    payload: CompanyDraftConfirmRequest | None = Body(default=None),
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> CompanyRead:
    _ = payload
    try:
        return confirm_company_draft(db, draft_id)
    except CompanyIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


@router.post("/drafts/{draft_id}/reject", response_model=CompanyDraftRead)
def reject_company_intake_draft(
    payload: CompanyDraftRejectRequest | None = Body(default=None),
    draft_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
) -> CompanyDraftRead:
    try:
        return reject_company_draft(db, draft_id, payload or CompanyDraftRejectRequest())
    except CompanyIntakeRequestError as exc:
        raise _intake_http_exception(exc) from exc


def _intake_http_exception(exc: CompanyIntakeRequestError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )
