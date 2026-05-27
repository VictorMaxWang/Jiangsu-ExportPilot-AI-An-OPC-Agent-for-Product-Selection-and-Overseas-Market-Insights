from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CompetitorItem
from app.schemas import CompetitorItemCreate, CompetitorItemUpdate


def count_competitor_items(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(CompetitorItem)) or 0


def list_competitor_items(db: Session, skip: int = 0, limit: int = 100) -> list[CompetitorItem]:
    statement = select(CompetitorItem).order_by(CompetitorItem.id).offset(skip).limit(limit)
    return list(db.scalars(statement))


def get_competitor_item(db: Session, competitor_item_id: int) -> CompetitorItem | None:
    return db.get(CompetitorItem, competitor_item_id)


def create_competitor_item(db: Session, payload: CompetitorItemCreate) -> CompetitorItem:
    item = CompetitorItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_competitor_item(
    db: Session,
    item: CompetitorItem,
    payload: CompetitorItemUpdate,
) -> CompetitorItem:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_competitor_item(db: Session, item: CompetitorItem) -> None:
    db.delete(item)
    db.commit()
