from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_countries: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    product_import_jobs: Mapped[list["ProductImportJob"]] = relationship(
        "ProductImportJob",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    product_drafts: Mapped[list["ProductDraft"]] = relationship(
        "ProductDraft",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    confirmed_company_drafts: Mapped[list["CompanyDraft"]] = relationship(
        "CompanyDraft",
        back_populates="confirmed_company",
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        "AnalysisRun",
        back_populates="company",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="company",
    )

