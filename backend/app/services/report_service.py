from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Report
from app.schemas import ReportCreate, ReportUpdate


def count_reports(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Report)) or 0


def list_reports(db: Session, skip: int = 0, limit: int = 100) -> list[Report]:
    statement = select(Report).order_by(Report.id).offset(skip).limit(limit)
    return list(db.scalars(statement))


def get_report(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)


def create_report(db: Session, payload: ReportCreate) -> Report:
    report = Report(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def update_report(db: Session, report: Report, payload: ReportUpdate) -> Report:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.commit()
    db.refresh(report)
    return report


def delete_report(db: Session, report: Report) -> None:
    db.delete(report)
    db.commit()
