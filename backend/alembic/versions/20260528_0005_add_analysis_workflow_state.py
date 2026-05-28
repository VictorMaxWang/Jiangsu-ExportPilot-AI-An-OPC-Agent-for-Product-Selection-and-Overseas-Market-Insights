"""add analysis workflow state

Revision ID: 20260528_0005
Revises: 20260528_0004
Create Date: 2026-05-28 12:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0005"
down_revision = "20260528_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("current_step", sa.String(length=128), nullable=True))
    op.add_column("analysis_runs", sa.Column("step_logs", sa.JSON(), nullable=True))
    op.add_column("analysis_runs", sa.Column("workflow_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_runs", "workflow_state")
    op.drop_column("analysis_runs", "step_logs")
    op.drop_column("analysis_runs", "current_step")
