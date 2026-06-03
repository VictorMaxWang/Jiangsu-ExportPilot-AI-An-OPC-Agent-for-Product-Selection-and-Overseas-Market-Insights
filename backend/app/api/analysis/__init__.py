from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import (
    AnalysisDetailResponse,
    AnalysisPerformanceResponse,
    AnalysisRunRequest,
    AnalysisRunStartResponse,
    AnalysisStatusResponse,
)
from app.services.agents import (
    ExportInsightWorkflow,
    WorkflowInputError,
    run_export_insight_workflow_background,
)
from app.services.ai import BailianClient
from app.services.data_sources import DataSourceService, get_data_source_service


router = APIRouter()
BackgroundRunner = Callable[[int], Awaitable[None]]


def get_export_insight_workflow(
    db: Session = Depends(get_db),
    data_source_service: DataSourceService = Depends(get_data_source_service),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> ExportInsightWorkflow:
    return ExportInsightWorkflow(db, data_source_service, ai_client=ai_client)


def get_analysis_background_runner() -> BackgroundRunner:
    return run_export_insight_workflow_background


@router.post("/run", response_model=AnalysisRunStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_analysis(
    request: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    workflow: ExportInsightWorkflow = Depends(get_export_insight_workflow),
    runner: BackgroundRunner = Depends(get_analysis_background_runner),
) -> AnalysisRunStartResponse:
    try:
        analysis_run = workflow.create_run(request)
    except WorkflowInputError as exc:
        raise _workflow_input_exception(exc) from exc

    background_tasks.add_task(runner, analysis_run.id)
    return workflow.start_response(analysis_run)


@router.get("/{analysis_id}/status", response_model=AnalysisStatusResponse)
def get_analysis_status(
    analysis_id: int,
    workflow: ExportInsightWorkflow = Depends(get_export_insight_workflow),
) -> AnalysisStatusResponse:
    response = workflow.status(analysis_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return response


@router.get("/{analysis_id}/performance", response_model=AnalysisPerformanceResponse)
def get_analysis_performance(
    analysis_id: int,
    workflow: ExportInsightWorkflow = Depends(get_export_insight_workflow),
) -> AnalysisPerformanceResponse:
    response = workflow.performance(analysis_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return response


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
def get_analysis_detail(
    analysis_id: int,
    workflow: ExportInsightWorkflow = Depends(get_export_insight_workflow),
) -> AnalysisDetailResponse:
    response = workflow.detail(analysis_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    return response


def _workflow_input_exception(exc: WorkflowInputError) -> HTTPException:
    if exc.code == "COMPANY_NOT_FOUND":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": exc.code, "message": str(exc)},
    )
