from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company
from app.schemas import CompanyCreate, CompanyUpdate


def count_companies(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Company)) or 0


def list_companies(db: Session, skip: int = 0, limit: int = 100) -> list[Company]:
    statement = select(Company).order_by(Company.id).offset(skip).limit(limit)
    return list(db.scalars(statement))


def get_company(db: Session, company_id: int) -> Company | None:
    return db.get(Company, company_id)


def create_company(db: Session, payload: CompanyCreate) -> Company:
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def update_company(db: Session, company: Company, payload: CompanyUpdate) -> Company:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


def delete_company(db: Session, company: Company) -> None:
    db.delete(company)
    db.commit()
