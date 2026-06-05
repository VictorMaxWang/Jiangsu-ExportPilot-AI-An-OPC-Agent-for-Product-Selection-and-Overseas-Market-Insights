from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_country_code(value: object) -> str:
    code = str(value or "").strip().upper()
    if len(code) not in {2, 3} or not code.isalpha():
        raise ValueError("country code must be a two- or three-letter ISO code")
    return code


class TargetCountryBase(BaseModel):
    country_code: str = Field(min_length=2, max_length=8)
    name_cn: str = Field(min_length=1, max_length=128)
    name_en: str = Field(min_length=1, max_length=128)
    region_code: str = Field(min_length=1, max_length=64)
    region_name_cn: str | None = Field(default=None, max_length=128)
    region_name_en: str | None = Field(default=None, max_length=128)
    continent: str | None = Field(default=None, max_length=64)
    currency_code: str | None = Field(default=None, max_length=16)
    languages: list[str] | None = None
    default_sort_order: int = Field(default=0, ge=0)
    enabled: bool = True
    analysis_enabled: bool = True
    disabled_reason: str | None = None
    provider_mappings: dict[str, Any] | None = None
    fallback_enabled: bool = True
    notes: str | None = None

    @field_validator("country_code", mode="before")
    @classmethod
    def _clean_country_code(cls, value: object) -> str:
        return _normalize_country_code(value)

    @field_validator("region_code", "currency_code", mode="before")
    @classmethod
    def _normalize_upper_optional(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("languages", mode="before")
    @classmethod
    def _clean_languages(cls, values: object) -> list[str] | None:
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
            cleaned.append(text)
            seen.add(dedupe_key)
        return cleaned


class TargetCountryCreate(TargetCountryBase):
    pass


class TargetCountryUpdate(BaseModel):
    country_code: str | None = Field(default=None, min_length=2, max_length=8)
    name_cn: str | None = Field(default=None, min_length=1, max_length=128)
    name_en: str | None = Field(default=None, min_length=1, max_length=128)
    region_code: str | None = Field(default=None, min_length=1, max_length=64)
    region_name_cn: str | None = Field(default=None, max_length=128)
    region_name_en: str | None = Field(default=None, max_length=128)
    continent: str | None = Field(default=None, max_length=64)
    currency_code: str | None = Field(default=None, max_length=16)
    languages: list[str] | None = None
    default_sort_order: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    analysis_enabled: bool | None = None
    disabled_reason: str | None = None
    provider_mappings: dict[str, Any] | None = None
    fallback_enabled: bool | None = None
    notes: str | None = None

    @field_validator("country_code", mode="before")
    @classmethod
    def _clean_country_code(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_country_code(value)


class TargetCountryRead(TargetCountryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AnalysisCountryPresetBase(BaseModel):
    preset_code: str = Field(min_length=1, max_length=64)
    name_cn: str = Field(min_length=1, max_length=128)
    name_en: str | None = Field(default=None, max_length=128)
    description: str | None = None
    country_codes: list[str] = Field(min_length=1)
    industry_tags: list[str] | None = None
    region_code: str | None = Field(default=None, max_length=64)
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0)
    enabled: bool = True

    @field_validator("preset_code", "region_code", mode="before")
    @classmethod
    def _normalize_code(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @field_validator("country_codes", mode="before")
    @classmethod
    def _clean_country_codes(cls, values: object) -> list[str]:
        if not isinstance(values, list):
            values = [values]
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            code = _normalize_country_code(value)
            if code in seen:
                continue
            cleaned.append(code)
            seen.add(code)
        if not cleaned:
            raise ValueError("country_codes must contain at least one country code")
        return cleaned


class AnalysisCountryPresetCreate(AnalysisCountryPresetBase):
    pass


class AnalysisCountryPresetUpdate(BaseModel):
    preset_code: str | None = Field(default=None, min_length=1, max_length=64)
    name_cn: str | None = Field(default=None, min_length=1, max_length=128)
    name_en: str | None = Field(default=None, max_length=128)
    description: str | None = None
    country_codes: list[str] | None = None
    industry_tags: list[str] | None = None
    region_code: str | None = Field(default=None, max_length=64)
    is_default: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    enabled: bool | None = None

    @field_validator("country_codes", mode="before")
    @classmethod
    def _clean_country_codes(cls, values: object) -> list[str] | None:
        if values is None:
            return None
        return AnalysisCountryPresetBase._clean_country_codes(values)


class AnalysisCountryPresetRead(AnalysisCountryPresetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
