from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin


class AnalysisRun(CreatedAtMixin, Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    input_products: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    target_countries: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="analysis_runs")
    opportunity_scores: Mapped[list["OpportunityScore"]] = relationship(
        "OpportunityScore",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )


class OpportunityScore(CreatedAtMixin, Base):
    __tablename__ = "opportunity_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    trend_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    price_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    market_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    supply_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    logistics_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    content_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True, index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis_run: Mapped[AnalysisRun] = relationship(
        "AnalysisRun",
        back_populates="opportunity_scores",
    )
    product: Mapped["Product"] = relationship("Product", back_populates="opportunity_scores")

