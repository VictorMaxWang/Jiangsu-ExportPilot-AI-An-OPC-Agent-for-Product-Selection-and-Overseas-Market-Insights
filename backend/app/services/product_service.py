from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Product
from app.schemas import ProductCreate, ProductUpdate


def company_exists(db: Session, company_id: int) -> bool:
    return db.get(Company, company_id) is not None


def count_products(db: Session, company_id: int | None = None) -> int:
    statement = select(func.count()).select_from(Product)
    if company_id is not None:
        statement = statement.where(Product.company_id == company_id)
    return db.scalar(statement) or 0


def list_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    company_id: int | None = None,
) -> list[Product]:
    statement = select(Product).order_by(Product.id).offset(skip).limit(limit)
    if company_id is not None:
        statement = statement.where(Product.company_id == company_id)
    return list(db.scalars(statement))


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product: Product, payload: ProductUpdate) -> Product:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    db.delete(product)
    db.commit()
