from __future__ import annotations

import asyncio
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Company, OpportunityScore, Product, Report
from app.schemas import AnalysisRunRequest
from app.services.agents import ExportInsightWorkflow
from app.services.ai import BailianChatCompletion
from app.services.data_sources import DataSourceService


def test_export_insight_workflow_completes_with_provider_and_ai_fallback(
    db_session: Session,
) -> None:
    company_id, product_id = _seed_product(db_session)
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=BadJsonAiClient(),
    )
    analysis_run = workflow.create_run(
        AnalysisRunRequest(
            company_id=company_id,
            product_ids=[product_id],
            target_countries=["US", "GB"],
            competitor_limit=8,
        )
    )

    status = asyncio.run(workflow.run(analysis_run.id))

    assert status is not None
    assert status.status == "fallback_used"
    assert status.current_step == "09_report_prep"
    assert len(status.step_logs) == 9
    assert all(step.status in {"success", "fallback_used"} for step in status.step_logs)
    assert status.scoring_summary.item_count == 2
    assert status.fallback_used_providers
    assert {"ebay", "rakuten", "reddit"}.isdisjoint(status.used_providers)

    score_count = db_session.scalar(select(func.count()).select_from(OpportunityScore))
    report_count = db_session.scalar(select(func.count()).select_from(Report))
    assert score_count == 2
    assert report_count == 1
    report = db_session.scalar(select(Report))
    assert report is not None
    assert report.title == "《南通家纺企业海外市场出海选品洞察报告》"
    assert report.content_markdown is not None
    assert "## 13. 下一步行动计划" in report.content_markdown
    assert report.content_html is not None

    detail = workflow.detail(analysis_run.id)
    assert detail is not None
    assert len(detail.scores) == 2
    assert len(detail.reports) == 1
    assert detail.marketing_assets
    assert detail.next_page_url == f"/reports?analysis_id={analysis_run.id}"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class FailingWorldBankProvider:
    async def fetch_country(self, _country_code: str) -> object:
        raise RuntimeError("worldbank unavailable")


class FailingUnComtradeProvider:
    async def get_trade_flow(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("un comtrade unavailable")


class FailingYoutubeProvider:
    async def search_videos(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("youtube unavailable")


class FailingGdeltProvider:
    async def search(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("gdelt unavailable")


class FailingEtsyProvider:
    async def search_listings(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("etsy unavailable")


class BadJsonAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        return BailianChatCompletion(content="not json", model="qwen3.6-plus")


def _failing_data_source_service(db: Session) -> DataSourceService:
    return DataSourceService(
        db,
        worldbank_provider=FailingWorldBankProvider(),
        un_comtrade_provider=FailingUnComtradeProvider(),
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
        etsy_provider=FailingEtsyProvider(),
    )


def _seed_product(db: Session) -> tuple[int, int]:
    company = Company(name="Jiangsu Demo Co", region="Jiangsu", industry="Home Textile")
    db.add(company)
    db.flush()
    product = Product(
        company_id=company.id,
        product_name_cn="Boho blanket sample",
        product_name_en="Boho Throw Blanket",
        category="Home Textile",
        cost_price_cny=Decimal("42.00"),
        weight_kg=Decimal("0.90"),
        package_size="35x28x12cm",
        material="Acrylic cotton blend",
        certification="OEKO-TEX",
        moq=120,
        description="Soft bohemian style throw blanket for sofa bedroom and gift sets",
    )
    db.add(product)
    db.commit()
    return company.id, product.id
