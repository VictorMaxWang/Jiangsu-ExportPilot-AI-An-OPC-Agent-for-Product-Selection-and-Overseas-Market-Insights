from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    company_id: int
    product_name_cn: str
    product_name_en: str | None = None
    category: str | None = None
    cost_price_cny: Decimal | None = None
    weight_kg: Decimal | None = None
    package_size: str | None = None
    material: str | None = None
    certification: str | None = None
    moq: int | None = None
    description: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    company_id: int | None = None
    product_name_cn: str | None = None
    product_name_en: str | None = None
    category: str | None = None
    cost_price_cny: Decimal | None = None
    weight_kg: Decimal | None = None
    package_size: str | None = None
    material: str | None = None
    certification: str | None = None
    moq: int | None = None
    description: str | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProductListItem(ProductRead):
    pass


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    total: int


class ProductKeywordBase(BaseModel):
    product_id: int
    keyword: str
    language: str | None = None
    country: str | None = None
    source: str | None = None


class ProductKeywordCreate(ProductKeywordBase):
    pass


class ProductKeywordUpdate(BaseModel):
    product_id: int | None = None
    keyword: str | None = None
    language: str | None = None
    country: str | None = None
    source: str | None = None


class ProductKeywordRead(ProductKeywordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ProductKeywordListItem(ProductKeywordRead):
    pass
