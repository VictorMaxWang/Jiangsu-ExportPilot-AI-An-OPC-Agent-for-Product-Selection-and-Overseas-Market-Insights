from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class CompanyImportJob(TimestampMixin, Base):
    __tablename__ = "company_import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)

    assets: Mapped[list["CompanyImportAsset"]] = relationship(
        "CompanyImportAsset",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["CompanyDraft"]] = relationship(
        "CompanyDraft",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )


class CompanyImportAsset(CreatedAtMixin, Base):
    __tablename__ = "company_import_assets"
    __table_args__ = (
        CheckConstraint("image_index >= 0", name="image_index_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("company_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_role: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    import_job: Mapped[CompanyImportJob] = relationship("CompanyImportJob", back_populates="assets")


class CompanyDraft(TimestampMixin, Base):
    __tablename__ = "company_drafts"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("company_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    credit_code_suffix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    main_products: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    risk_notes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    confirmed_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    import_job: Mapped[CompanyImportJob] = relationship("CompanyImportJob", back_populates="drafts")
    confirmed_company: Mapped["Company | None"] = relationship(
        "Company",
        back_populates="confirmed_company_drafts",
    )
