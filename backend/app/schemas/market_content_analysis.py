from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.countries import DEFAULT_TARGET_COUNTRIES, normalize_country_codes


class AnalysisSource(BaseModel):
    provider: str
    source_label: str
    source_type: str
    fallback_used: bool = False
    api_invoked: bool = False
    detail: str | None = None


class SuitableProductItem(BaseModel):
    product_key: str
    product_name_cn: str
    product_name_en: str
    category: str
    hs_code: str
    fit_score: int = Field(ge=0, le=100)
    reason: str
    evidence: list[str] = Field(default_factory=list)


class MarketProfileAnalysisResponse(BaseModel):
    provider: Literal["market_profile_analysis"] = "market_profile_analysis"
    country_code: str
    country_name: str | None = None
    product_category: str
    keyword: str | None = None
    hs_code: str | None = None
    market_size_score: int = Field(ge=0, le=100)
    consumption_power_score: int = Field(ge=0, le=100)
    internet_score: int = Field(ge=0, le=100)
    trade_score: int = Field(ge=0, le=100)
    logistics_score: int = Field(ge=0, le=100)
    competition_level: Literal["low", "medium", "high", "unknown"]
    suitable_products: list[SuitableProductItem] = Field(default_factory=list)
    summary: str
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class MarketCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_category: str = Field(min_length=1)
    country_codes: list[str] = Field(default_factory=lambda: list(DEFAULT_TARGET_COUNTRIES))
    keyword: str | None = Field(default=None, min_length=1)
    hs_code: str | None = Field(default=None, min_length=1, max_length=16)

    @field_validator("country_codes")
    @classmethod
    def _clean_country_codes(cls, values: list[str]) -> list[str]:
        return normalize_country_codes(values, field_name="country_codes")


class MarketCompareResponse(BaseModel):
    provider: Literal["market_profile_analysis"] = "market_profile_analysis"
    product_category: str
    keyword: str | None = None
    hs_code: str | None = None
    items: list[MarketProfileAnalysisResponse]
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)


class ContentTrendAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=3)


class ContentTrendSourceItem(BaseModel):
    platform: str
    country: str | None = None
    keyword: str
    title: str
    url: str | None = None
    channel_or_community: str | None = None
    published_at: str | None = None
    heat_score: Decimal | None = None
    summary: str | None = None
    content_style: str | None = None
    source_type: str
    source_label: str
    api_invoked: bool = False
    fallback_used: bool = False
    sample_notice: str | None = None


class ContentTrendAnalysisResponse(BaseModel):
    provider: Literal["content_trend_analysis"] = "content_trend_analysis"
    keyword: str
    country: str
    content_themes: list[str] = Field(default_factory=list)
    marketing_angles: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    video_script_ideas: list[str] = Field(default_factory=list)
    pinterest_keywords: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    source_items: list[ContentTrendSourceItem] = Field(default_factory=list)
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)
