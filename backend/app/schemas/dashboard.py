from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class DashboardProductScore(BaseModel):
    product_id: int
    product_name_cn: str
    product_name_en: str | None = None
    country: str
    keyword: str | None = None
    rank: int | None = None
    total_score: Decimal | None = None
    trend_score: Decimal | None = None
    price_score: Decimal | None = None
    market_score: Decimal | None = None
    supply_score: Decimal | None = None
    logistics_score: Decimal | None = None
    content_score: Decimal | None = None
    fallback_used: bool = False
    ai_fallback_used: bool = False


class DashboardCountryScore(BaseModel):
    country: str
    average_score: Decimal | None = None
    top_score: Decimal | None = None
    recommendation_count: int = Field(ge=0)
    top_product_id: int | None = None
    top_product_name: str | None = None


class DashboardPriceRange(BaseModel):
    product_id: int
    product_name: str
    country: str
    keyword: str | None = None
    min_price: Decimal | None = None
    median_price: Decimal | None = None
    avg_price: Decimal | None = None
    max_price: Decimal | None = None
    currency: str | None = None
    item_count: int = Field(default=0, ge=0)
    competition_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    price_suggestion: str | None = None
    sample_notice: str


class DashboardContentTheme(BaseModel):
    theme: str
    weight: int = Field(ge=1)
    product_id: int | None = None
    country: str | None = None
    keyword: str | None = None
    source_item_count: int = Field(default=0, ge=0)


class DashboardRecommendation(BaseModel):
    rank: int | None = None
    product_id: int
    product_name: str
    country: str
    total_score: Decimal | None = None
    reason: str | None = None
    next_action: str | None = None
    fallback_used: bool = False
    ai_fallback_used: bool = False


class DashboardRiskCard(BaseModel):
    title: str
    severity: Literal["low", "medium", "high"]
    product_id: int | None = None
    product_name: str | None = None
    country: str | None = None
    message: str
    source: str


class DashboardDataSourceUsed(BaseModel):
    provider: str
    label: str
    source_type: str
    fallback_used: bool = False
    api_invoked: bool = False
    detail: str | None = None


class DashboardResponse(BaseModel):
    analysis_id: int
    product_scores: list[DashboardProductScore] = Field(default_factory=list)
    country_scores: list[DashboardCountryScore] = Field(default_factory=list)
    price_ranges: list[DashboardPriceRange] = Field(default_factory=list)
    content_themes: list[DashboardContentTheme] = Field(default_factory=list)
    top_recommendations: list[DashboardRecommendation] = Field(default_factory=list)
    risk_cards: list[DashboardRiskCard] = Field(default_factory=list)
    data_sources_used: list[DashboardDataSourceUsed] = Field(default_factory=list)
