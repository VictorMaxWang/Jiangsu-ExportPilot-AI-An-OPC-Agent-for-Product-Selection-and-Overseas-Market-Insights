from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.market_content_analysis import AnalysisSource


CompetitionLevel = Literal["low", "medium", "high"]


class OpportunityExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    next_action: str = Field(min_length=1)


class CompetitorAnalysisResult(BaseModel):
    keyword: str
    country: str
    item_count: int = Field(ge=0)
    min_price: Decimal = Field(ge=0)
    median_price: Decimal = Field(ge=0)
    max_price: Decimal = Field(ge=0)
    avg_price: Decimal = Field(ge=0)
    currency: str
    common_terms: list[str] = Field(default_factory=list)
    competition_level: CompetitionLevel
    price_suggestion: str
    summary: str


class OpportunityScoreResult(BaseModel):
    id: int | None = None
    analysis_id: int
    product_id: int
    product_name_cn: str
    product_name_en: str | None = None
    country: str
    keyword: str
    trend_score: Decimal = Field(ge=0, le=100)
    price_score: Decimal = Field(ge=0, le=100)
    market_score: Decimal = Field(ge=0, le=100)
    supply_score: Decimal = Field(ge=0, le=100)
    logistics_score: Decimal = Field(ge=0, le=100)
    content_score: Decimal = Field(ge=0, le=100)
    total_score: Decimal = Field(ge=0, le=100)
    rank: int = Field(ge=1)
    reason: str
    risk: str
    next_action: str
    competitor_analysis: CompetitorAnalysisResult
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScoringRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(ge=1)
    product_ids: list[int] | None = None
    target_countries: list[str] = Field(default_factory=lambda: ["US", "GB", "JP", "AU", "SG"])
    competitor_limit: int = Field(default=20, ge=1, le=50)

    @field_validator("product_ids")
    @classmethod
    def _clean_product_ids(cls, values: list[int] | None) -> list[int] | None:
        if values is None:
            return None
        cleaned: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value < 1:
                raise ValueError("product_ids must contain positive integers")
            if value not in seen:
                cleaned.append(value)
                seen.add(value)
        return cleaned

    @field_validator("target_countries")
    @classmethod
    def _clean_target_countries(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip().upper()
            if len(normalized) not in {2, 3} or not normalized.isalpha():
                raise ValueError("target_countries must contain two- or three-letter country codes")
            if normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        if not cleaned:
            raise ValueError("At least one target country is required")
        return cleaned


class ScoringRunResponse(BaseModel):
    provider: Literal["opportunity_scoring"] = "opportunity_scoring"
    analysis_id: int
    company_id: int
    status: str
    item_count: int = Field(ge=0)
    items: list[OpportunityScoreResult]
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)


class ScoringResultsResponse(BaseModel):
    provider: Literal["opportunity_scoring"] = "opportunity_scoring"
    analysis_id: int
    company_id: int
    status: str
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    item_count: int = Field(ge=0)
    items: list[OpportunityScoreResult]
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[AnalysisSource] = Field(default_factory=list)
