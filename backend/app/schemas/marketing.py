from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FORBIDDEN_MARKETING_CLAIMS = (
    "sales forecast",
    "sales prediction",
    "profit guarantee",
    "guaranteed conversion",
    "guaranteed sales",
    "best-selling",
    "bestseller",
    "no.1",
    "no 1",
    "100% safe",
    "customs cleared",
    "销量预测",
    "爆款预测",
    "销售额预测",
    "利润预测",
)


class MarketingGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str = Field(min_length=1)
    country: str = Field(min_length=2, max_length=3)
    target_users: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    price_range: str | None = Field(default=None, min_length=1)
    content_themes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    analysis_id: int | None = Field(default=None, ge=1)
    score_id: int | None = Field(default=None, ge=1)
    persist_to_analysis: bool = False

    @field_validator("product", "price_range", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("country")
    @classmethod
    def _normalize_country(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) not in {2, 3} or not normalized.isalpha():
            raise ValueError("country must be a two- or three-letter country code")
        return normalized

    @field_validator("target_users", "selling_points", "content_themes", "risk_notes")
    @classmethod
    def _clean_string_list(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class MarketingGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    bullet_points: list[str] = Field(min_length=5, max_length=5)
    seo_keywords: list[str] = Field(default_factory=list)
    short_video_script: str = Field(min_length=1)
    pinterest_keywords: list[str] = Field(default_factory=list)
    platform_listing_advice: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)

    @field_validator("title", "short_video_script", "platform_listing_advice")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("field must not be empty")
        return cleaned

    @field_validator("bullet_points", "seo_keywords", "pinterest_keywords", "risk_notes")
    @classmethod
    def _clean_response_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)

    @model_validator(mode="after")
    def _reject_unsafe_claims(self) -> "MarketingGenerateResponse":
        content = " ".join(
            [
                self.title,
                *self.bullet_points,
                *self.seo_keywords,
                self.short_video_script,
                *self.pinterest_keywords,
                self.platform_listing_advice,
                *self.risk_notes,
            ]
        ).casefold()
        for claim in FORBIDDEN_MARKETING_CLAIMS:
            if claim.casefold() in content:
                raise ValueError(f"unsafe marketing claim detected: {claim}")
        return self


MarketingRiskCategory = Literal[
    "data_limit",
    "claim_verification",
    "platform_policy",
    "localization",
    "certification",
    "logistics",
    "pricing",
    "ai_fallback",
]


def _clean_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.strip().split())
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned
