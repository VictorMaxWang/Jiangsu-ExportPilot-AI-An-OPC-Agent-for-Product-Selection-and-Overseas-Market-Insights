from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Product, ProductKeyword
from app.schemas import ProductCreate, ProductUpdate
from app.schemas.ai import ProductKeywordsResponse


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


def persist_generated_keywords(
    db: Session,
    product: Product,
    result: ProductKeywordsResponse,
    *,
    target_country: str | None = None,
) -> int:
    saved_count = 0
    existing = {
        (language or "", keyword.casefold())
        for keyword, language in db.execute(
            select(ProductKeyword.keyword, ProductKeyword.language).where(
                ProductKeyword.product_id == product.id,
            )
        )
    }

    product.product_name_en = result.product_name_en
    for language, keywords in (("en", result.keywords_en), ("ja", result.keywords_jp)):
        for keyword in keywords:
            normalized = keyword.strip()
            if not normalized:
                continue
            dedupe_key = (language, normalized.casefold())
            if dedupe_key in existing:
                continue
            db.add(
                ProductKeyword(
                    product_id=product.id,
                    keyword=normalized,
                    language=language,
                    country=target_country,
                    source="bailian",
                )
            )
            existing.add(dedupe_key)
            saved_count += 1

    db.commit()
    db.refresh(product)
    return saved_count
