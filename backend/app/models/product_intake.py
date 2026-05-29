from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class ProductImportJob(TimestampMixin, Base):
    __tablename__ = "product_import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_platform: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="product_import_jobs")
    assets: Mapped[list["ProductImportAsset"]] = relationship(
        "ProductImportAsset",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["ProductDraft"]] = relationship(
        "ProductDraft",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )
    domestic_links: Mapped[list["DomesticProductLink"]] = relationship(
        "DomesticProductLink",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )


class ProductImportAsset(CreatedAtMixin, Base):
    __tablename__ = "product_import_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("product_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    import_job: Mapped[ProductImportJob] = relationship("ProductImportJob", back_populates="assets")


class DomesticProductLink(TimestampMixin, Base):
    __tablename__ = "domestic_product_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("product_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", index=True)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sku_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    parsed_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_job: Mapped[ProductImportJob] = relationship("ProductImportJob", back_populates="domestic_links")


class ProductDraft(TimestampMixin, Base):
    __tablename__ = "product_drafts"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("product_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name_cn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price_cny: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_price_cny: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    package_size: Mapped[str | None] = mapped_column(String(128), nullable=True)
    material: Mapped[str | None] = mapped_column(String(128), nullable=True)
    color_options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    selling_points: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    target_users: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    confirmed_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    import_job: Mapped[ProductImportJob] = relationship("ProductImportJob", back_populates="drafts")
    company: Mapped["Company"] = relationship("Company", back_populates="product_drafts")
    confirmed_product: Mapped["Product | None"] = relationship("Product", back_populates="confirmed_drafts")
