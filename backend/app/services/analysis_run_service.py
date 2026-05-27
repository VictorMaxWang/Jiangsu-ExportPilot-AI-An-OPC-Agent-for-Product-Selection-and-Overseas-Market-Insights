from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun
from app.schemas import AnalysisRunCreate, AnalysisRunUpdate


def count_analysis_runs(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(AnalysisRun)) or 0


def list_analysis_runs(db: Session, skip: int = 0, limit: int = 100) -> list[AnalysisRun]:
    statement = select(AnalysisRun).order_by(AnalysisRun.id).offset(skip).limit(limit)
    return list(db.scalars(statement))


def get_analysis_run(db: Session, analysis_run_id: int) -> AnalysisRun | None:
    return db.get(AnalysisRun, analysis_run_id)


def create_analysis_run(db: Session, payload: AnalysisRunCreate) -> AnalysisRun:
    analysis_run = AnalysisRun(**payload.model_dump())
    db.add(analysis_run)
    db.commit()
    db.refresh(analysis_run)
    return analysis_run


def update_analysis_run(
    db: Session,
    analysis_run: AnalysisRun,
    payload: AnalysisRunUpdate,
) -> AnalysisRun:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(analysis_run, field, value)
    db.commit()
    db.refresh(analysis_run)
    return analysis_run


def delete_analysis_run(db: Session, analysis_run: AnalysisRun) -> None:
    db.delete(analysis_run)
    db.commit()
