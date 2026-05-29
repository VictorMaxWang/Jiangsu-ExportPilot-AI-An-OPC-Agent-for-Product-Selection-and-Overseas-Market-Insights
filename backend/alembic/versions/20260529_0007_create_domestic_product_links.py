"""create domestic product links

Revision ID: 20260529_0007
Revises: 20260529_0006
Create Date: 2026-05-29 16:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0007"
down_revision = "20260529_0006"
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
        "domestic_product_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=True),
        sa.Column("item_id", sa.String(length=128), nullable=True),
        sa.Column("sku_id", sa.String(length=128), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parsed_title", sa.String(length=512), nullable=True),
        sa.Column("parsed_text", sa.Text(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["product_import_jobs.id"],
            name=op.f("fk_domestic_product_links_import_job_id_product_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domestic_product_links")),
    )
    op.create_index(
        op.f("ix_domestic_product_links_import_job_id"),
        "domestic_product_links",
        ["import_job_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_domestic_product_links_item_id"),
        "domestic_product_links",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_domestic_product_links_parse_status"),
        "domestic_product_links",
        ["parse_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_domestic_product_links_platform"),
        "domestic_product_links",
        ["platform"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("domestic_product_links")
