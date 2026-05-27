from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisRunBase(BaseModel):
    company_id: int
    status: str = "pending"
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRunCreate(AnalysisRunBase):
    pass


class AnalysisRunUpdate(BaseModel):
    company_id: int | None = None
    status: str | None = None
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRunRead(AnalysisRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class AnalysisRunListItem(AnalysisRunRead):
    pass


class OpportunityScoreBase(BaseModel):
    analysis_id: int
    product_id: int
    country: str
    trend_score: Decimal | None = None
    price_score: Decimal | None = None
    market_score: Decimal | None = None
    supply_score: Decimal | None = None
    logistics_score: Decimal | None = None
    content_score: Decimal | None = None
    total_score: Decimal | None = None
    rank: int | None = None
    reason: str | None = None
    risk: str | None = None


class OpportunityScoreCreate(OpportunityScoreBase):
    pass


class OpportunityScoreUpdate(BaseModel):
    analysis_id: int | None = None
    product_id: int | None = None
    country: str | None = None
    trend_score: Decimal | None = None
    price_score: Decimal | None = None
    market_score: Decimal | None = None
    supply_score: Decimal | None = None
    logistics_score: Decimal | None = None
    content_score: Decimal | None = None
    total_score: Decimal | None = None
    rank: int | None = None
    reason: str | None = None
    risk: str | None = None


class OpportunityScoreRead(OpportunityScoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class OpportunityScoreListItem(OpportunityScoreRead):
    pass
