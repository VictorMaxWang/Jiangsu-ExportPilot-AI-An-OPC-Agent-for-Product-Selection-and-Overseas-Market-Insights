"""create data source caches and api call logs

Revision ID: 20260528_0003
Revises: 20260527_0002
Create Date: 2026-05-28 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0003"
down_revision = "20260527_0002"
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
        "data_source_caches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_caches")),
        sa.UniqueConstraint(
            "provider",
            "endpoint",
            "query",
            "country",
            name="uq_data_source_caches_provider_endpoint_query_country",
        ),
    )
    op.create_index(op.f("ix_data_source_caches_country"), "data_source_caches", ["country"], unique=False)
    op.create_index(op.f("ix_data_source_caches_endpoint"), "data_source_caches", ["endpoint"], unique=False)
    op.create_index(op.f("ix_data_source_caches_expires_at"), "data_source_caches", ["expires_at"], unique=False)
    op.create_index(op.f("ix_data_source_caches_provider"), "data_source_caches", ["provider"], unique=False)
    op.create_index(op.f("ix_data_source_caches_query"), "data_source_caches", ["query"], unique=False)

    op.create_table(
        "api_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_call_logs")),
    )
    op.create_index(op.f("ix_api_call_logs_called_at"), "api_call_logs", ["called_at"], unique=False)
    op.create_index(op.f("ix_api_call_logs_endpoint"), "api_call_logs", ["endpoint"], unique=False)
    op.create_index(op.f("ix_api_call_logs_provider"), "api_call_logs", ["provider"], unique=False)
    op.create_index(op.f("ix_api_call_logs_status"), "api_call_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_call_logs_status"), table_name="api_call_logs")
    op.drop_index(op.f("ix_api_call_logs_provider"), table_name="api_call_logs")
    op.drop_index(op.f("ix_api_call_logs_endpoint"), table_name="api_call_logs")
    op.drop_index(op.f("ix_api_call_logs_called_at"), table_name="api_call_logs")
    op.drop_table("api_call_logs")

    op.drop_index(op.f("ix_data_source_caches_query"), table_name="data_source_caches")
    op.drop_index(op.f("ix_data_source_caches_provider"), table_name="data_source_caches")
    op.drop_index(op.f("ix_data_source_caches_expires_at"), table_name="data_source_caches")
    op.drop_index(op.f("ix_data_source_caches_endpoint"), table_name="data_source_caches")
    op.drop_index(op.f("ix_data_source_caches_country"), table_name="data_source_caches")
    op.drop_table("data_source_caches")
