"""create youtube search caches

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27 21:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_0002"
down_revision = "20260527_0001"
branch_labels = None
depends_on = None


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "youtube_search_caches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_search_caches")),
        sa.UniqueConstraint("keyword", "country", name="uq_youtube_search_caches_keyword_country"),
    )
    op.create_index(
        op.f("ix_youtube_search_caches_country"),
        "youtube_search_caches",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_youtube_search_caches_expires_at"),
        "youtube_search_caches",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_youtube_search_caches_keyword"),
        "youtube_search_caches",
        ["keyword"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_youtube_search_caches_keyword"), table_name="youtube_search_caches")
    op.drop_index(op.f("ix_youtube_search_caches_expires_at"), table_name="youtube_search_caches")
    op.drop_index(op.f("ix_youtube_search_caches_country"), table_name="youtube_search_caches")
    op.drop_table("youtube_search_caches")
