"""extend opportunity scores for R16

Revision ID: 20260528_0004
Revises: 20260528_0003
Create Date: 2026-05-28 11:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunity_scores", sa.Column("next_action", sa.Text(), nullable=True))
    op.add_column(
        "opportunity_scores",
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("ai_fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("opportunity_scores", sa.Column("sources", sa.JSON(), nullable=True))
    op.add_column("opportunity_scores", sa.Column("evidence", sa.JSON(), nullable=True))
    op.add_column("opportunity_scores", sa.Column("competitor_analysis", sa.JSON(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("opportunity_scores", "fallback_used", server_default=None)
        op.alter_column("opportunity_scores", "ai_fallback_used", server_default=None)


def downgrade() -> None:
    op.drop_column("opportunity_scores", "competitor_analysis")
    op.drop_column("opportunity_scores", "evidence")
    op.drop_column("opportunity_scores", "sources")
    op.drop_column("opportunity_scores", "ai_fallback_used")
    op.drop_column("opportunity_scores", "fallback_used")
    op.drop_column("opportunity_scores", "next_action")
