"""q41 upgrade database models

Revision ID: 20260604_0008
Revises: 20260529_0007
Create Date: 2026-06-04 20:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0008"
down_revision = "20260529_0007"
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
    _extend_product_intake_tables()
    _create_company_intake_tables()
    _create_target_market_tables()
    _create_chat_and_report_versioning_tables()
    _backfill_report_versions()


def downgrade() -> None:
    _drop_chat_and_report_versioning_tables()
    _drop_target_market_tables()
    _drop_company_intake_tables()
    _rollback_product_intake_extensions()


def _extend_product_intake_tables() -> None:
    with op.batch_alter_table("product_import_assets") as batch_op:
        batch_op.add_column(sa.Column("image_index", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("image_role", sa.String(length=64), server_default="unknown", nullable=False))
        batch_op.add_column(sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.create_check_constraint(
            op.f("ck_product_import_assets_image_index_nonnegative"),
            "image_index >= 0",
        )
        batch_op.create_index(op.f("ix_product_import_assets_image_role"), ["image_role"], unique=False)

    op.execute(
        """
        UPDATE product_import_assets
        SET is_primary = TRUE
        WHERE id IN (
            SELECT MIN(id)
            FROM product_import_assets
            GROUP BY import_job_id
        )
        """
    )

    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.add_column(sa.Column("image_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("primary_image_asset_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("multi_image_summary", sa.JSON(), nullable=True))
        batch_op.create_check_constraint(
            op.f("ck_product_drafts_image_count_nonnegative"),
            "image_count >= 0",
        )
        batch_op.create_foreign_key(
            op.f("fk_product_drafts_primary_image_asset_id_product_import_assets"),
            "product_import_assets",
            ["primary_image_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_product_drafts_primary_image_asset_id"),
            ["primary_image_asset_id"],
            unique=False,
        )

    op.execute(
        """
        UPDATE product_drafts
        SET image_count = (
            SELECT COUNT(*)
            FROM product_import_assets
            WHERE product_import_assets.import_job_id = product_drafts.import_job_id
        )
        """
    )
    op.execute(
        """
        UPDATE product_drafts
        SET primary_image_asset_id = (
            SELECT product_import_assets.id
            FROM product_import_assets
            WHERE product_import_assets.import_job_id = product_drafts.import_job_id
              AND product_import_assets.is_primary = TRUE
            ORDER BY product_import_assets.id
            LIMIT 1
        )
        """
    )


def _create_company_intake_tables() -> None:
    op.create_table(
        "company_import_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_import_jobs")),
    )
    op.create_index(op.f("ix_company_import_jobs_source_platform"), "company_import_jobs", ["source_platform"])
    op.create_index(op.f("ix_company_import_jobs_source_type"), "company_import_jobs", ["source_type"])
    op.create_index(op.f("ix_company_import_jobs_status"), "company_import_jobs", ["status"])

    op.create_table(
        "company_import_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("image_index", sa.Integer(), nullable=False),
        sa.Column("image_role", sa.String(length=64), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        created_at_column(),
        sa.CheckConstraint("image_index >= 0", name=op.f("ck_company_import_assets_image_index_nonnegative")),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["company_import_jobs.id"],
            name=op.f("fk_company_import_assets_import_job_id_company_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_import_assets")),
    )
    op.create_index(op.f("ix_company_import_assets_image_role"), "company_import_assets", ["image_role"])
    op.create_index(op.f("ix_company_import_assets_import_job_id"), "company_import_assets", ["import_job_id"])

    op.create_table(
        "company_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("credit_code_suffix", sa.String(length=32), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("main_products", sa.JSON(), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_role", sa.String(length=128), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("risk_notes", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confirmed_company_id", sa.Integer(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name=op.f("ck_company_drafts_confidence_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_company_id"],
            ["companies.id"],
            name=op.f("fk_company_drafts_confirmed_company_id_companies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["company_import_jobs.id"],
            name=op.f("fk_company_drafts_import_job_id_company_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_drafts")),
    )
    op.create_index(op.f("ix_company_drafts_company_name"), "company_drafts", ["company_name"])
    op.create_index(op.f("ix_company_drafts_confirmed_company_id"), "company_drafts", ["confirmed_company_id"])
    op.create_index(op.f("ix_company_drafts_import_job_id"), "company_drafts", ["import_job_id"])
    op.create_index(op.f("ix_company_drafts_industry"), "company_drafts", ["industry"])
    op.create_index(op.f("ix_company_drafts_status"), "company_drafts", ["status"])


def _create_target_market_tables() -> None:
    op.create_table(
        "target_countries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("name_cn", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=False),
        sa.Column("region_code", sa.String(length=64), nullable=False),
        sa.Column("region_name_cn", sa.String(length=128), nullable=True),
        sa.Column("region_name_en", sa.String(length=128), nullable=True),
        sa.Column("continent", sa.String(length=64), nullable=True),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=True),
        sa.Column("default_sort_order", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("analysis_enabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("provider_mappings", sa.JSON(), nullable=True),
        sa.Column("fallback_enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_target_countries")),
        sa.UniqueConstraint("country_code", name=op.f("uq_target_countries_country_code")),
    )
    op.create_index(op.f("ix_target_countries_analysis_enabled"), "target_countries", ["analysis_enabled"])
    op.create_index(op.f("ix_target_countries_continent"), "target_countries", ["continent"])
    op.create_index(op.f("ix_target_countries_country_code"), "target_countries", ["country_code"])
    op.create_index(op.f("ix_target_countries_enabled"), "target_countries", ["enabled"])
    op.create_index(op.f("ix_target_countries_region_code"), "target_countries", ["region_code"])

    op.create_table(
        "analysis_country_presets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("preset_code", sa.String(length=64), nullable=False),
        sa.Column("name_cn", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("country_codes", sa.JSON(), nullable=False),
        sa.Column("industry_tags", sa.JSON(), nullable=True),
        sa.Column("region_code", sa.String(length=64), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_country_presets")),
        sa.UniqueConstraint("preset_code", name=op.f("uq_analysis_country_presets_preset_code")),
    )
    op.create_index(op.f("ix_analysis_country_presets_enabled"), "analysis_country_presets", ["enabled"])
    op.create_index(op.f("ix_analysis_country_presets_is_default"), "analysis_country_presets", ["is_default"])
    op.create_index(op.f("ix_analysis_country_presets_preset_code"), "analysis_country_presets", ["preset_code"])
    op.create_index(op.f("ix_analysis_country_presets_region_code"), "analysis_country_presets", ["region_code"])


def _create_chat_and_report_versioning_tables() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("current_page", sa.String(length=128), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("context_refs", sa.JSON(), nullable=True),
        sa.Column("safety_status", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(["analysis_id"], ["analysis_runs.id"], name=op.f("fk_chat_sessions_analysis_id_analysis_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_chat_sessions_company_id_companies"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_chat_sessions_product_id_products"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name=op.f("fk_chat_sessions_report_id_reports"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_sessions")),
    )
    op.create_index(op.f("ix_chat_sessions_analysis_id"), "chat_sessions", ["analysis_id"])
    op.create_index(op.f("ix_chat_sessions_company_id"), "chat_sessions", ["company_id"])
    op.create_index(op.f("ix_chat_sessions_current_page"), "chat_sessions", ["current_page"])
    op.create_index(op.f("ix_chat_sessions_product_id"), "chat_sessions", ["product_id"])
    op.create_index(op.f("ix_chat_sessions_report_id"), "chat_sessions", ["report_id"])
    op.create_index(op.f("ix_chat_sessions_safety_status"), "chat_sessions", ["safety_status"])
    op.create_index(op.f("ix_chat_sessions_status"), "chat_sessions", ["status"])

    op.create_table(
        "report_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_proposal_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("version_note", sa.Text(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(["parent_version_id"], ["report_versions.id"], name=op.f("fk_report_versions_parent_version_id_report_versions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name=op.f("fk_report_versions_report_id_reports"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_versions")),
        sa.UniqueConstraint("report_id", "version_number", name=op.f("uq_report_versions_report_id_version_number")),
    )
    op.create_index(op.f("ix_report_versions_parent_version_id"), "report_versions", ["parent_version_id"])
    op.create_index(op.f("ix_report_versions_report_id"), "report_versions", ["report_id"])
    op.create_index(op.f("ix_report_versions_source_proposal_id"), "report_versions", ["source_proposal_id"])
    op.create_index(op.f("ix_report_versions_source_type"), "report_versions", ["source_type"])

    op.create_table(
        "report_edit_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("target_version_id", sa.Integer(), nullable=True),
        sa.Column("source_chat_session_id", sa.Integer(), nullable=True),
        sa.Column("user_intent", sa.Text(), nullable=False),
        sa.Column("proposed_markdown", sa.Text(), nullable=True),
        sa.Column("proposed_html", sa.Text(), nullable=True),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("replacement_blocks", sa.JSON(), nullable=True),
        sa.Column("risk_notes", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("accepted_version_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name=op.f("ck_report_edit_proposals_confidence_score_range"),
        ),
        sa.ForeignKeyConstraint(["accepted_version_id"], ["report_versions.id"], name=op.f("fk_report_edit_proposals_accepted_version_id_report_versions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name=op.f("fk_report_edit_proposals_report_id_reports"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chat_session_id"], ["chat_sessions.id"], name=op.f("fk_report_edit_proposals_source_chat_session_id_chat_sessions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_version_id"], ["report_versions.id"], name=op.f("fk_report_edit_proposals_target_version_id_report_versions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_edit_proposals")),
    )
    op.create_index(op.f("ix_report_edit_proposals_accepted_version_id"), "report_edit_proposals", ["accepted_version_id"])
    op.create_index(op.f("ix_report_edit_proposals_report_id"), "report_edit_proposals", ["report_id"])
    op.create_index(op.f("ix_report_edit_proposals_source_chat_session_id"), "report_edit_proposals", ["source_chat_session_id"])
    op.create_index(op.f("ix_report_edit_proposals_status"), "report_edit_proposals", ["status"])
    op.create_index(op.f("ix_report_edit_proposals_target_version_id"), "report_edit_proposals", ["target_version_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_redacted", sa.Boolean(), nullable=False),
        sa.Column("context_refs", sa.JSON(), nullable=True),
        sa.Column("safety_status", sa.String(length=32), nullable=False),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_edit_proposal_id", sa.Integer(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(["report_edit_proposal_id"], ["report_edit_proposals.id"], name=op.f("fk_chat_messages_report_edit_proposal_id_report_edit_proposals"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name=op.f("fk_chat_messages_session_id_chat_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(op.f("ix_chat_messages_report_edit_proposal_id"), "chat_messages", ["report_edit_proposal_id"])
    op.create_index(op.f("ix_chat_messages_role"), "chat_messages", ["role"])
    op.create_index(op.f("ix_chat_messages_safety_status"), "chat_messages", ["safety_status"])
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"])

    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("current_version_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_reports_current_version_id_report_versions"),
            "report_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_reports_current_version_id"), ["current_version_id"], unique=False)


def _backfill_report_versions() -> None:
    op.execute(
        """
        INSERT INTO report_versions (
            report_id,
            version_number,
            content_markdown,
            content_html,
            source_type,
            source_proposal_id,
            created_by,
            version_note,
            created_at
        )
        SELECT
            id,
            1,
            content_markdown,
            content_html,
            'generated',
            NULL,
            'migration',
            'Backfilled from reports table.',
            created_at
        FROM reports
        """
    )
    op.execute(
        """
        UPDATE reports
        SET current_version_id = (
            SELECT report_versions.id
            FROM report_versions
            WHERE report_versions.report_id = reports.id
              AND report_versions.version_number = 1
            ORDER BY report_versions.id
            LIMIT 1
        )
        """
    )


def _drop_chat_and_report_versioning_tables() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_index(op.f("ix_reports_current_version_id"))
        batch_op.drop_constraint(op.f("fk_reports_current_version_id_report_versions"), type_="foreignkey")
        batch_op.drop_column("current_version_id")

    op.drop_table("chat_messages")
    op.drop_table("report_edit_proposals")
    op.drop_table("report_versions")
    op.drop_table("chat_sessions")


def _drop_target_market_tables() -> None:
    op.drop_table("analysis_country_presets")
    op.drop_table("target_countries")


def _drop_company_intake_tables() -> None:
    op.drop_table("company_drafts")
    op.drop_table("company_import_assets")
    op.drop_table("company_import_jobs")


def _rollback_product_intake_extensions() -> None:
    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.drop_index(op.f("ix_product_drafts_primary_image_asset_id"))
        batch_op.drop_constraint(op.f("fk_product_drafts_primary_image_asset_id_product_import_assets"), type_="foreignkey")
        batch_op.drop_constraint(op.f("ck_product_drafts_image_count_nonnegative"), type_="check")
        batch_op.drop_column("multi_image_summary")
        batch_op.drop_column("primary_image_asset_id")
        batch_op.drop_column("image_count")

    with op.batch_alter_table("product_import_assets") as batch_op:
        batch_op.drop_index(op.f("ix_product_import_assets_image_role"))
        batch_op.drop_constraint(op.f("ck_product_import_assets_image_index_nonnegative"), type_="check")
        batch_op.drop_column("is_primary")
        batch_op.drop_column("image_role")
        batch_op.drop_column("image_index")
