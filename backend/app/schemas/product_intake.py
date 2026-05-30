from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


SourcePlatform = Literal["taobao", "tmall", "pinduoduo", "jd", "unknown"]
AiResultType = Literal["real_qwen", "fallback", "manual_required"]
EvidenceSource = Literal[
    "screenshot_text",
    "screenshot_visual",
    "url_text",
    "manual_text",
    "model_inference",
]

_ALLOWED_PLATFORMS = {"taobao", "tmall", "pinduoduo", "jd", "unknown"}


class ProductIntakeEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=128)
    source: EvidenceSource
    value: str | None = Field(default=None, max_length=240)

    @field_validator("field", "value", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class QwenProductUnderstandingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_platform: SourcePlatform = "unknown"
    product_name_cn: str | None = None
    product_name_en: str | None = None
    category: str | None = None
    price_cny: Decimal | None = Field(default=None, ge=0)
    material: str | None = None
    specification: str | None = None
    dimensions: str | None = None
    weight_estimate: str | None = None
    color_options: list[str] = Field(default_factory=list)
    selling_points_cn: list[str] = Field(default_factory=list)
    selling_points_en: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    usage_scenarios: list[str] = Field(default_factory=list)
    cross_border_keywords_en: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    confidence_score: Decimal = Field(ge=0, le=1)
    evidence: list[ProductIntakeEvidenceItem] = Field(default_factory=list)

    @field_validator("source_platform", mode="before")
    @classmethod
    def _normalize_platform(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        return text if text in _ALLOWED_PLATFORMS else "unknown"

    @field_validator(
        "product_name_cn",
        "product_name_en",
        "category",
        "material",
        "specification",
        "dimensions",
        "weight_estimate",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator(
        "color_options",
        "selling_points_cn",
        "selling_points_en",
        "target_users",
        "usage_scenarios",
        "cross_border_keywords_en",
        "risk_notes",
        mode="before",
    )
    @classmethod
    def _clean_string_list(cls, values: object) -> list[str]:
        if values is None or values == "":
            return []
        if not isinstance(values, list):
            values = [values]
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            dedupe_key = text.casefold()
            if dedupe_key in seen:
                continue
            cleaned.append(text)
            seen.add(dedupe_key)
        return cleaned


class ProductImportAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    created_at: datetime


class DomesticProductLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    normalized_url: str | None = None
    item_id: str | None = None
    sku_id: str | None = None
    parse_status: str
    parsed_title: str | None = None
    parse_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductDraftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    product_name_cn: str | None = None
    product_name_en: str | None = None
    category: str | None = None
    price_cny: Decimal | None = None
    confidence_score: Decimal | None = None
    confirmed_product_id: int | None = None

    @computed_field
    @property
    def low_confidence(self) -> bool:
        if self.confidence_score is None:
            return True
        return self.confidence_score < Decimal("0.65")


class ProductDraftRead(ProductDraftSummary):
    import_job_id: int
    company_id: int
    cost_price_cny: Decimal | None = None
    weight_kg: Decimal | None = None
    package_size: str | None = None
    material: str | None = None
    color_options: list[str] | None = None
    specification: str | None = None
    selling_points: dict[str, Any] | None = None
    target_users: list[str] | None = None
    source_platform: str | None = None
    evidence: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime


class ProductDraftListResponse(BaseModel):
    items: list[ProductDraftRead]
    total: int
    limit: int
    offset: int


class ProductDraftSellingPointsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selling_points_cn: list[str] | None = Field(default=None, max_length=20)
    selling_points_en: list[str] | None = Field(default=None, max_length=20)
    usage_scenarios: list[str] | None = Field(default=None, max_length=20)
    cross_border_keywords_en: list[str] | None = Field(default=None, max_length=20)
    risk_notes: list[str] | None = Field(default=None, max_length=20)

    @field_validator(
        "selling_points_cn",
        "selling_points_en",
        "usage_scenarios",
        "cross_border_keywords_en",
        "risk_notes",
        mode="before",
    )
    @classmethod
    def _clean_optional_string_list(cls, values: object) -> list[str] | None:
        if values is None:
            return []
        if values == "":
            return []
        if not isinstance(values, list):
            values = [values]
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            dedupe_key = text.casefold()
            if dedupe_key in seen:
                continue
            cleaned.append(text[:180])
            seen.add(dedupe_key)
        return cleaned


class ProductDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name_cn: str | None = Field(default=None, max_length=255)
    product_name_en: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=128)
    price_cny: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    cost_price_cny: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    weight_kg: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    package_size: str | None = Field(default=None, max_length=128)
    material: str | None = Field(default=None, max_length=128)
    color_options: list[str] | None = Field(default=None, max_length=20)
    specification: str | None = Field(default=None, max_length=4000)
    selling_points: ProductDraftSellingPointsUpdate | None = None
    target_users: list[str] | None = Field(default=None, max_length=20)
    risk_notes: list[str] | None = Field(default=None, max_length=20)
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    evidence: list[ProductIntakeEvidenceItem] | None = Field(default=None, max_length=50)

    @field_validator(
        "product_name_cn",
        "product_name_en",
        "category",
        "package_size",
        "material",
        "specification",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("color_options", "target_users", "risk_notes", mode="before")
    @classmethod
    def _clean_optional_string_list(cls, values: object) -> list[str] | None:
        if values is None:
            return []
        if values == "":
            return []
        if not isinstance(values, list):
            values = [values]
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            dedupe_key = text.casefold()
            if dedupe_key in seen:
                continue
            cleaned.append(text[:180])
            seen.add(dedupe_key)
        return cleaned


class ProductDraftConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(gt=0)


class ProductDraftRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ProductImportJobDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    source_type: str
    source_platform: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    model_used: str | None = None
    created_at: datetime
    updated_at: datetime
    assets: list[ProductImportAssetRead] = Field(default_factory=list)
    domestic_links: list[DomesticProductLinkRead] = Field(default_factory=list)
    drafts: list[ProductDraftSummary] = Field(default_factory=list)


class ProductScreenshotIntakeResponse(BaseModel):
    import_job_id: int
    draft_id: int
    job_status: str
    draft_status: str
    low_confidence: bool
    ai_result_type: AiResultType
    ai_fallback_used: bool
    model_used: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    next_action: Literal["review_draft", "manual_review", "manual_fill"]
    asset: ProductImportAssetRead
    draft: ProductDraftSummary


class ProductUrlIntakeRequest(BaseModel):
    company_id: int = Field(gt=0)
    url: str = Field(min_length=1, max_length=2048)


class ProductUrlIntakeResponse(BaseModel):
    job_id: int
    draft_id: int
    status: Literal["draft_ready", "needs_screenshot", "failed"]
    parse_status: str
    source_platform: str
    normalized_url: str | None = None
    item_id: str | None = None
    sku_id: str | None = None
    message: str
    ai_result_type: AiResultType
    ai_fallback_used: bool
    model_used: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    draft: ProductDraftRead
