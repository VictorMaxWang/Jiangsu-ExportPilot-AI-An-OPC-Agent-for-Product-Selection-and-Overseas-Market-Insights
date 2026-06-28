from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import ProductKeywordsResponse


class ProductBase(BaseModel):
    company_id: int
    product_name_cn: str = Field(min_length=1)
    product_name_en: str | None = None
    category: str | None = None
    cost_price_cny: Decimal | None = Field(default=None, ge=0)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    package_size: str | None = None
    material: str | None = None
    certification: str | None = None
    moq: int | None = Field(default=None, ge=0)
    description: str | None = None

    @field_validator("product_name_cn", mode="before")
    @classmethod
    def _strip_product_name_cn(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    company_id: int | None = None
    product_name_cn: str | None = Field(default=None, min_length=1)
    product_name_en: str | None = None
    category: str | None = None
    cost_price_cny: Decimal | None = Field(default=None, ge=0)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    package_size: str | None = None
    material: str | None = None
    certification: str | None = None
    moq: int | None = Field(default=None, ge=0)
    description: str | None = None

    @field_validator("product_name_cn", mode="before")
    @classmethod
    def _strip_product_name_cn(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


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


class ProductKeywordGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_country: str | None = None
    target_platforms: list[str] = Field(default_factory=list)
    persist: bool = True


class ProductKeywordGenerationResponse(ProductKeywordsResponse):
    saved_keywords_count: int = 0
