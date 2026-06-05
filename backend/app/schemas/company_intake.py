from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class CompanyImportAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    image_index: int = 0
    image_role: str = "unknown"
    is_primary: bool = False
    created_at: datetime


class CompanyDraftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    company_name: str | None = None
    region: str | None = None
    industry: str | None = None
    confidence_score: Decimal | None = None
    confirmed_company_id: int | None = None

    @computed_field
    @property
    def low_confidence(self) -> bool:
        if self.confidence_score is None:
            return True
        return self.confidence_score < Decimal("0.65")


class CompanyDraftRead(CompanyDraftSummary):
    import_job_id: int
    credit_code_suffix: str | None = None
    main_products: list[str] | None = None
    website: str | None = None
    description: str | None = None
    contact_role: str | None = None
    evidence: list[dict[str, Any]] | None = None
    risk_notes: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class CompanyImportJobDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_platform: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    model_used: str | None = None
    created_at: datetime
    updated_at: datetime
    assets: list[CompanyImportAssetRead] = Field(default_factory=list)
    drafts: list[CompanyDraftSummary] = Field(default_factory=list)


class CompanyDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, max_length=255)
    credit_code_suffix: str | None = Field(default=None, max_length=32)
    region: str | None = Field(default=None, max_length=128)
    industry: str | None = Field(default=None, max_length=128)
    main_products: list[str] | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=2048)
    description: str | None = Field(default=None, max_length=4000)
    contact_role: str | None = Field(default=None, max_length=128)
    evidence: list[dict[str, Any]] | None = Field(default=None, max_length=80)
    risk_notes: list[str] | None = Field(default=None, max_length=30)
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)

    @field_validator(
        "company_name",
        "credit_code_suffix",
        "region",
        "industry",
        "website",
        "description",
        "contact_role",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("main_products", "risk_notes", mode="before")
    @classmethod
    def _clean_string_list(cls, values: object) -> list[str] | None:
        if values is None:
            return None
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
