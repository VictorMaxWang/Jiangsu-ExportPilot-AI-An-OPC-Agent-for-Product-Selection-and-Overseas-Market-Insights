"""q47 company photo intake

Revision ID: 20260605_0009
Revises: 20260604_0008
Create Date: 2026-06-05 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_0009"
down_revision = "20260604_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("company_drafts") as batch_op:
        batch_op.add_column(sa.Column("target_countries", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("company_drafts") as batch_op:
        batch_op.drop_column("target_countries")
