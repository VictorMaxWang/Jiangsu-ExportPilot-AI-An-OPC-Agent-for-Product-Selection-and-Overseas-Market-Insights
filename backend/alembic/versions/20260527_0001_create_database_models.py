"""create database models

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_0001"
down_revision = None
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
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_countries", sa.JSON(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index(op.f("ix_companies_industry"), "companies", ["industry"], unique=False)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("product_name_cn", sa.String(length=255), nullable=False),
        sa.Column("product_name_en", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("cost_price_cny", sa.Numeric(12, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("package_size", sa.String(length=128), nullable=True),
        sa.Column("material", sa.String(length=128), nullable=True),
        sa.Column("certification", sa.String(length=255), nullable=True),
        sa.Column("moq", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_products_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(op.f("ix_products_category"), "products", ["category"], unique=False)
    op.create_index(op.f("ix_products_company_id"), "products", ["company_id"], unique=False)
    op.create_index(
        op.f("ix_products_product_name_cn"),
        "products",
        ["product_name_cn"],
        unique=False,
    )

    op.create_table(
        "product_keywords",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_keywords_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_keywords")),
    )
    op.create_index(
        op.f("ix_product_keywords_keyword"),
        "product_keywords",
        ["keyword"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_keywords_product_id"),
        "product_keywords",
        ["product_id"],
        unique=False,
    )

    op.create_table(
        "api_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("key_name", sa.String(length=128), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_test_status", sa.String(length=64), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_credentials")),
    )
    op.create_index(
        op.f("ix_api_credentials_provider"),
        "api_credentials",
        ["provider"],
        unique=False,
    )

    op.create_table(
        "competitor_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("product_url", sa.String(length=2048), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("seller_location", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitor_items")),
    )
    op.create_index(
        op.f("ix_competitor_items_country"),
        "competitor_items",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitor_items_keyword"),
        "competitor_items",
        ["keyword"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitor_items_platform"),
        "competitor_items",
        ["platform"],
        unique=False,
    )

    op.create_table(
        "market_indicators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=16), nullable=False),
        sa.Column("country_name", sa.String(length=128), nullable=False),
        sa.Column("indicator_code", sa.String(length=128), nullable=False),
        sa.Column("indicator_name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_indicators")),
    )
    op.create_index(
        op.f("ix_market_indicators_country_code"),
        "market_indicators",
        ["country_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_market_indicators_indicator_code"),
        "market_indicators",
        ["indicator_code"],
        unique=False,
    )
    op.create_index(op.f("ix_market_indicators_year"), "market_indicators", ["year"], unique=False)

    op.create_table(
        "trade_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hs_code", sa.String(length=32), nullable=False),
        sa.Column("product_category", sa.String(length=255), nullable=True),
        sa.Column("reporter", sa.String(length=128), nullable=False),
        sa.Column("partner", sa.String(length=128), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("flow", sa.String(length=64), nullable=False),
        sa.Column("trade_value_usd", sa.Numeric(18, 2), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_stats")),
    )
    op.create_index(op.f("ix_trade_stats_hs_code"), "trade_stats", ["hs_code"], unique=False)
    op.create_index(op.f("ix_trade_stats_partner"), "trade_stats", ["partner"], unique=False)
    op.create_index(op.f("ix_trade_stats_reporter"), "trade_stats", ["reporter"], unique=False)
    op.create_index(op.f("ix_trade_stats_year"), "trade_stats", ["year"], unique=False)

    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(length=64), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_items")),
    )
    op.create_index(op.f("ix_news_items_country"), "news_items", ["country"], unique=False)
    op.create_index(op.f("ix_news_items_query"), "news_items", ["query"], unique=False)
    op.create_index(op.f("ix_news_items_source"), "news_items", ["source"], unique=False)

    op.create_table(
        "content_trends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("channel_or_community", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heat_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_style", sa.String(length=128), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_trends")),
    )
    op.create_index(
        op.f("ix_content_trends_country"),
        "content_trends",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_trends_keyword"),
        "content_trends",
        ["keyword"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_trends_platform"),
        "content_trends",
        ["platform"],
        unique=False,
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("input_products", sa.JSON(), nullable=True),
        sa.Column("target_countries", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_analysis_runs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        op.f("ix_analysis_runs_company_id"),
        "analysis_runs",
        ["company_id"],
        unique=False,
    )
    op.create_index(op.f("ix_analysis_runs_status"), "analysis_runs", ["status"], unique=False)

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=False),
        sa.Column("trend_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("price_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("market_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("supply_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("logistics_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("content_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("risk", sa.Text(), nullable=True),
        created_at_column(),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis_runs.id"],
            name=op.f("fk_opportunity_scores_analysis_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_opportunity_scores_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunity_scores")),
    )
    op.create_index(
        op.f("ix_opportunity_scores_analysis_id"),
        "opportunity_scores",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunity_scores_country"),
        "opportunity_scores",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunity_scores_product_id"),
        "opportunity_scores",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_opportunity_scores_total_score"),
        "opportunity_scores",
        ["total_score"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.String(length=2048), nullable=True),
        created_at_column(),
        updated_at_column(),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis_runs.id"],
            name=op.f("fk_reports_analysis_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_reports_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_analysis_id"), "reports", ["analysis_id"], unique=False)
    op.create_index(op.f("ix_reports_company_id"), "reports", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("opportunity_scores")
    op.drop_table("analysis_runs")
    op.drop_table("content_trends")
    op.drop_table("news_items")
    op.drop_table("trade_stats")
    op.drop_table("market_indicators")
    op.drop_table("competitor_items")
    op.drop_table("api_credentials")
    op.drop_table("product_keywords")
    op.drop_table("products")
    op.drop_table("companies")
