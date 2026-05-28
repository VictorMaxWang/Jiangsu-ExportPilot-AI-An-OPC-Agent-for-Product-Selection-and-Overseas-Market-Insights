from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalysisRunBase(BaseModel):
    company_id: int
    status: str = "pending"
    current_step: str | None = None
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    step_logs: list[dict[str, Any]] | None = None
    workflow_state: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRunCreate(AnalysisRunBase):
    pass


class AnalysisRunUpdate(BaseModel):
    company_id: int | None = None
    status: str | None = None
    current_step: str | None = None
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    step_logs: list[dict[str, Any]] | None = None
    workflow_state: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisRunRead(AnalysisRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class AnalysisRunListItem(AnalysisRunRead):
    pass


class AnalysisRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(ge=1)
    product_ids: list[int] = Field(min_length=1)
    target_countries: list[str] = Field(min_length=1)
    competitor_limit: int = Field(default=20, ge=1, le=50)

    @field_validator("product_ids")
    @classmethod
    def _clean_product_ids(cls, values: list[int]) -> list[int]:
        cleaned: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value < 1:
                raise ValueError("product_ids must contain positive integers")
            if value not in seen:
                cleaned.append(value)
                seen.add(value)
        if not cleaned:
            raise ValueError("At least one product is required")
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


class AnalysisStepLog(BaseModel):
    step_id: str
    node: str
    title: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ProviderBreakdownItem(BaseModel):
    provider: str
    source_types: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    api_invoked: bool = False
    fallback_used: bool = False


class ScoringSummary(BaseModel):
    item_count: int = Field(default=0, ge=0)
    top_score: Decimal | None = None
    top_product_id: int | None = None
    top_country: str | None = None
    fallback_used: bool = False
    ai_fallback_used: bool = False


class AnalysisRunStartResponse(BaseModel):
    provider: str = "export_insight_workflow"
    analysis_id: int
    status: str
    current_step: str | None = None
    status_url: str
    detail_url: str
    next_page_url: str | None = None


class AnalysisStatusResponse(BaseModel):
    provider: str = "export_insight_workflow"
    analysis_id: int
    company_id: int
    status: str
    current_step: str | None = None
    step_logs: list[AnalysisStepLog] = Field(default_factory=list)
    scoring_summary: ScoringSummary = Field(default_factory=ScoringSummary)
    used_providers: list[str] = Field(default_factory=list)
    fallback_used_providers: list[str] = Field(default_factory=list)
    provider_breakdown: list[ProviderBreakdownItem] = Field(default_factory=list)
    next_page_url: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AnalysisDetailResponse(AnalysisStatusResponse):
    input_products: list[dict[str, Any]] | None = None
    target_countries: list[str] | None = None
    scores: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    marketing_assets: list[dict[str, Any]] = Field(default_factory=list)
    workflow_state: dict[str, Any] = Field(default_factory=dict)


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
    next_action: str | None = None
    fallback_used: bool = False
    ai_fallback_used: bool = False
    sources: list[dict[str, Any]] | None = None
    evidence: dict[str, Any] | None = None
    competitor_analysis: dict[str, Any] | None = None


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
    next_action: str | None = None
    fallback_used: bool | None = None
    ai_fallback_used: bool | None = None
    sources: list[dict[str, Any]] | None = None
    evidence: dict[str, Any] | None = None
    competitor_analysis: dict[str, Any] | None = None


class OpportunityScoreRead(OpportunityScoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class OpportunityScoreListItem(OpportunityScoreRead):
    pass
