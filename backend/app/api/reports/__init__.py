from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    ReportEditProposalRead,
    ReportGenerateRequest,
    ReportListResponse,
    ReportProposalConfirmResponse,
    ReportProposalDecisionRequest,
    ReportRead,
    ReportVersionListResponse,
    ReportVersionRead,
    ReportVersionRestoreRequest,
    ReportVersionRestoreResponse,
)
from app.services import report_service
from app.services.report_service import ReportVersioningError
from app.services.ai import BailianClient
from app.services.reports import ReportGenerationInputError, ReportGenerator


router = APIRouter()


def get_report_generator(
    db: Session = Depends(get_db),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> ReportGenerator:
    return ReportGenerator(db, ai_client=ai_client)


@router.post("/generate", response_model=ReportRead)
async def generate_report(
    request: ReportGenerateRequest,
    service: ReportGenerator = Depends(get_report_generator),
) -> ReportRead:
    try:
        outcome = await service.generate_from_analysis(
            request.analysis_id,
            force_regenerate=request.force_regenerate,
        )
    except ReportGenerationInputError as exc:
        raise _input_exception(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "REPORT_GENERATION_FAILED", "message": "报告生成失败，可重新生成报告。"},
        ) from exc
    return outcome.report


@router.get("", response_model=ReportListResponse)
def list_reports(
    analysis_id: int | None = Query(default=None, ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    return ReportListResponse(
        items=report_service.list_reports(db, skip=skip, limit=limit, analysis_id=analysis_id),
        total=report_service.count_reports(db, analysis_id=analysis_id),
    )


@router.get("/{report_id}", response_model=ReportRead)
def get_report(report_id: int, db: Session = Depends(get_db)) -> ReportRead:
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/{report_id}/versions", response_model=ReportVersionListResponse)
def list_report_versions(report_id: int, db: Session = Depends(get_db)) -> ReportVersionListResponse:
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    versions = report_service.list_report_versions(db, report_id)
    return ReportVersionListResponse(
        items=[ReportVersionRead.model_validate(version) for version in versions],
        total=len(versions),
        current_version_id=report.current_version_id,
    )


@router.post("/proposals/{proposal_id}/confirm", response_model=ReportProposalConfirmResponse)
def confirm_report_edit_proposal(
    proposal_id: int,
    payload: ReportProposalDecisionRequest = Body(default_factory=ReportProposalDecisionRequest),
    db: Session = Depends(get_db),
) -> ReportProposalConfirmResponse:
    try:
        report, version, proposal = report_service.confirm_report_edit_proposal(
            db,
            proposal_id,
            decision_note=payload.reason,
        )
    except ReportVersioningError as exc:
        raise _versioning_exception(exc) from exc
    return ReportProposalConfirmResponse(
        report=ReportRead.model_validate(report),
        version=ReportVersionRead.model_validate(version),
        proposal=ReportEditProposalRead.model_validate(proposal),
    )


@router.post("/proposals/{proposal_id}/reject", response_model=ReportEditProposalRead)
def reject_report_edit_proposal(
    proposal_id: int,
    payload: ReportProposalDecisionRequest = Body(default_factory=ReportProposalDecisionRequest),
    db: Session = Depends(get_db),
) -> ReportEditProposalRead:
    try:
        proposal = report_service.reject_report_edit_proposal(db, proposal_id, decision_note=payload.reason)
    except ReportVersioningError as exc:
        raise _versioning_exception(exc) from exc
    return ReportEditProposalRead.model_validate(proposal)


@router.post("/{report_id}/versions/{version_id}/restore", response_model=ReportVersionRestoreResponse)
def restore_report_version(
    report_id: int,
    version_id: int,
    payload: ReportVersionRestoreRequest = Body(default_factory=ReportVersionRestoreRequest),
    db: Session = Depends(get_db),
) -> ReportVersionRestoreResponse:
    try:
        report, version = report_service.restore_report_version(
            db,
            report_id,
            version_id,
            decision_note=payload.reason,
        )
    except ReportVersioningError as exc:
        raise _versioning_exception(exc) from exc
    return ReportVersionRestoreResponse(
        report=ReportRead.model_validate(report),
        version=ReportVersionRead.model_validate(version),
    )


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    format: str = Query(default="markdown", pattern="^(markdown|html|pdf)$"),
    db: Session = Depends(get_db),
) -> Response:
    report = report_service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if format == "pdf":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF export is not implemented in v1",
        )
    if format == "html":
        content = report.content_html or ""
        media_type = "text/html; charset=utf-8"
        filename = f"report-{report.id}.html"
    else:
        content = report.content_markdown or ""
        media_type = "text/markdown; charset=utf-8"
        filename = f"report-{report.id}.md"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _input_exception(exc: ReportGenerationInputError) -> HTTPException:
    if exc.code in {"ANALYSIS_NOT_FOUND", "COMPANY_NOT_FOUND"}:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": str(exc)})
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": str(exc)})


def _versioning_exception(exc: ReportVersioningError) -> HTTPException:
    if exc.code in {"REPORT_NOT_FOUND", "REPORT_VERSION_NOT_FOUND", "REPORT_PROPOSAL_NOT_FOUND"}:
        code = status.HTTP_404_NOT_FOUND
    elif exc.code in {"REPORT_PROPOSAL_STALE", "REPORT_VERSION_ALREADY_CURRENT"}:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail: dict[str, object] = {"code": exc.code, "message": str(exc)}
    if exc.quality is not None:
        detail["quality"] = exc.quality
    return HTTPException(status_code=code, detail=detail)
