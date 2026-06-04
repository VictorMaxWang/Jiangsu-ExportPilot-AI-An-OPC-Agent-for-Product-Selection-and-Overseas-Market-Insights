from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    ReportGenerateRequest,
    ReportListResponse,
    ReportRead,
)
from app.services import report_service
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
