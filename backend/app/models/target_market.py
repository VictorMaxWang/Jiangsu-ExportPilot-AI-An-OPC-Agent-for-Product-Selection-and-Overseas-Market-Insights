from __future__ import annotations

from sqlalchemy import Boolean, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TargetCountry(TimestampMixin, Base):
    __tablename__ = "target_countries"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_target_countries_country_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    name_cn: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    region_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region_name_cn: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region_name_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    continent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    languages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    default_sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    analysis_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_mappings: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnalysisCountryPreset(TimestampMixin, Base):
    __tablename__ = "analysis_country_presets"
    __table_args__ = (
        UniqueConstraint("preset_code", name="uq_analysis_country_presets_preset_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preset_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name_cn: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    industry_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    region_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
