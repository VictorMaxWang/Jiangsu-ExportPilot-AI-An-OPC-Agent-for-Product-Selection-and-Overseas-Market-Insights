"""create product intake tables

Revision ID: 20260529_0006
Revises: 20260528_0005
Create Date: 2026-05-29 15:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0006"
down_revision = "20260528_0005"
branch_labels = None
depends_on = None


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "product_import_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_platform", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_product_import_jobs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_import_jobs")),
    )
    op.create_index(
        op.f("ix_product_import_jobs_company_id"),
        "product_import_jobs",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_import_jobs_company_id_status",
        "product_import_jobs",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_import_jobs_created_at"),
        "product_import_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_import_jobs_source_platform"),
        "product_import_jobs",
        ["source_platform"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_import_jobs_source_type"),
        "product_import_jobs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_import_jobs_status"),
        "product_import_jobs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "product_import_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["product_import_jobs.id"],
            name=op.f("fk_product_import_assets_import_job_id_product_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_import_assets")),
    )
    op.create_index(
        op.f("ix_product_import_assets_import_job_id"),
        "product_import_assets",
        ["import_job_id"],
        unique=False,
    )

    op.create_table(
        "product_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("product_name_cn", sa.String(length=255), nullable=True),
        sa.Column("product_name_en", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("price_cny", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_price_cny", sa.Numeric(12, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("package_size", sa.String(length=128), nullable=True),
        sa.Column("material", sa.String(length=128), nullable=True),
        sa.Column("color_options", sa.JSON(), nullable=True),
        sa.Column("specification", sa.Text(), nullable=True),
        sa.Column("selling_points", sa.JSON(), nullable=True),
        sa.Column("target_users", sa.JSON(), nullable=True),
        sa.Column("source_platform", sa.String(length=32), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confirmed_product_id", sa.Integer(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name=op.f("ck_product_drafts_confidence_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_product_drafts_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_product_id"],
            ["products.id"],
            name=op.f("fk_product_drafts_confirmed_product_id_products"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["product_import_jobs.id"],
            name=op.f("fk_product_drafts_import_job_id_product_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_drafts")),
    )
    op.create_index(
        op.f("ix_product_drafts_company_id"),
        "product_drafts",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_drafts_company_id_status",
        "product_drafts",
        ["company_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_drafts_confirmed_product_id"),
        "product_drafts",
        ["confirmed_product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_drafts_import_job_id"),
        "product_drafts",
        ["import_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_drafts_status"),
        "product_drafts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("product_drafts")
    op.drop_table("product_import_assets")
    op.drop_table("product_import_jobs")
