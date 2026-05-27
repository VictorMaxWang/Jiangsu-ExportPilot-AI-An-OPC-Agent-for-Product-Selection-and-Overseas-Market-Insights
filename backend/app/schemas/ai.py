from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AiChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class AiChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[AiChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1200, ge=1, le=8192)
    json_mode: bool = False


class AiChatResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, Any] | None = None


class ProductKeywordsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name_cn: str = Field(min_length=1)
    product_name_en: str | None = None
    category: str | None = None
    material: str | None = None
    certification: str | None = None
    cost_price_cny: str | None = None
    weight_kg: str | None = None
    package_size: str | None = None
    moq: int | None = Field(default=None, ge=1)
    description: str | None = None
    target_country: str | None = None
    target_platforms: list[str] = Field(default_factory=list)


class ProductKeywordsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name_en: str
    keywords_en: list[str]
    keywords_jp: list[str]
    target_users: list[str]
    selling_points: list[str]
    risk_notes: list[str]

    @field_validator(
        "keywords_en",
        "keywords_jp",
        "target_users",
        "selling_points",
        "risk_notes",
    )
    @classmethod
    def _clean_string_list(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped:
                continue
            dedupe_key = stripped.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(stripped)
        return cleaned


class MarketingCopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    product_description: str | None = None
    target_country: str = Field(min_length=1)
    target_language: Literal["en", "ja", "zh"] = "en"
    platform: str | None = None
    tone: str = "professional"
    keywords: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)


class MarketingCopyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_title: str
    short_description: str
    bullet_points: list[str] = Field(default_factory=list)
    ad_copy: str
    social_posts: list[str] = Field(default_factory=list)
    seo_keywords: list[str] = Field(default_factory=list)
    localization_notes: list[str] = Field(default_factory=list)


class ReportSectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_type: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    target_country: str | None = None
    market_context: dict[str, Any] = Field(default_factory=dict)
    language: Literal["zh", "en"] = "zh"


class ReportSectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_title: str
    content_markdown: str
