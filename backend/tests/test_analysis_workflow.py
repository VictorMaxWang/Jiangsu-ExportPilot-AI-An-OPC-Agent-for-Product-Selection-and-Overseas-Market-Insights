from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Company, OpportunityScore, Product, ProductDraft, ProductImportJob, ProductKeyword, Report
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


def test_workflow_generates_missing_import_product_keywords_and_preserves_intake_evidence(
    db_session: Session,
) -> None:
    company_id, product_id = _seed_imported_product_missing_keywords(db_session)
    ai_client = KeywordThenBadJsonAiClient()
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=ai_client,
    )
    analysis_run = workflow.create_run(
        AnalysisRunRequest(
            company_id=company_id,
            product_ids=[product_id],
            target_countries=["US"],
            competitor_limit=8,
        )
    )

    status = asyncio.run(workflow.run(analysis_run.id))

    assert status is not None
    assert status.status == "fallback_used"
    assert ai_client.keyword_calls == 1

    product = db_session.get(Product, product_id)
    assert product is not None
    assert product.product_name_en == "Pet Cooling Mat"
    keywords = list(
        db_session.scalars(
            select(ProductKeyword.keyword).where(ProductKeyword.product_id == product_id).order_by(ProductKeyword.id)
        )
    )
    assert keywords == ["pet cooling mat", "summer pet mat"]

    refreshed_run = db_session.get(type(analysis_run), analysis_run.id)
    assert refreshed_run is not None
    product_profile = (refreshed_run.workflow_state or {})["product_profiles"][0]
    assert product_profile["keyword"] == "pet cooling mat"
    assert product_profile["keyword_source"] == "bailian_generated"
    assert product_profile["product_keywords"] == ["pet cooling mat", "summer pet mat"]
    assert product_profile["intake_source"]["source_platform"] == "jd"
    assert product_profile["intake_source"]["source_url"] == "https://item.jd.com/100012043978.html"
    assert product_profile["intake_source"]["low_confidence"] is True

    score = db_session.scalar(select(OpportunityScore).where(OpportunityScore.analysis_id == analysis_run.id))
    assert score is not None
    assert score.evidence["product_keywords"] == ["pet cooling mat", "summer pet mat"]
    assert score.evidence["intake_source"]["source_platform"] == "jd"
    assert "secret-token" not in json.dumps(score.evidence, ensure_ascii=False)

    report = db_session.scalar(select(Report).where(Report.analysis_id == analysis_run.id))
    assert report is not None
    assert report.content_markdown is not None
    assert "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。" in report.content_markdown
    assert "secret-token" not in report.content_markdown


def test_workflow_uses_deterministic_keyword_when_qwen_keyword_generation_fails(
    db_session: Session,
) -> None:
    company = Company(name="Jiangsu Manual Co", region="Jiangsu", industry="Home Textile")
    db_session.add(company)
    db_session.flush()
    product = Product(
        company_id=company.id,
        product_name_cn="人工确认宠物垫",
        product_name_en=None,
        category="宠物用品",
        package_size="40x30x4cm",
        material="Nylon",
        description="Imported from low confidence product intake.",
    )
    db_session.add(product)
    db_session.commit()

    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=BadJsonAiClient(),
    )
    analysis_run = workflow.create_run(
        AnalysisRunRequest(
            company_id=company.id,
            product_ids=[product.id],
            target_countries=["US"],
            competitor_limit=8,
        )
    )

    status = asyncio.run(workflow.run(analysis_run.id))

    assert status is not None
    assert status.status == "fallback_used"
    refreshed_run = db_session.get(type(analysis_run), analysis_run.id)
    assert refreshed_run is not None
    product_profile = (refreshed_run.workflow_state or {})["product_profiles"][0]
    assert product_profile["keyword"] == "宠物用品"
    assert product_profile["keyword_source"] == "product_fields_fallback"
    assert db_session.scalar(select(OpportunityScore).where(OpportunityScore.analysis_id == analysis_run.id)) is not None


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


class KeywordThenBadJsonAiClient:
    def __init__(self) -> None:
        self.keyword_calls = 0

    async def chat(self, messages: list[dict[str, str]], *args: object, **kwargs: object) -> BailianChatCompletion:
        prompt_text = "\n".join(message.get("content", "") for message in messages)
        if "keywords_en" in prompt_text and "product_name_en" in prompt_text and self.keyword_calls == 0:
            self.keyword_calls += 1
            return BailianChatCompletion(
                content=json.dumps(
                    {
                        "product_name_en": "Pet Cooling Mat",
                        "keywords_en": ["pet cooling mat", "summer pet mat"],
                        "keywords_jp": ["ペット 冷感 マット"],
                        "target_users": ["Pet owners"],
                        "selling_points": ["Cool-touch surface"],
                        "risk_notes": ["Verify material before launch."],
                    },
                    ensure_ascii=False,
                ),
                model="qwen3.6-plus",
            )
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


def _seed_imported_product_missing_keywords(db: Session) -> tuple[int, int]:
    company = Company(name="Jiangsu Intake Co", region="Jiangsu", industry="Pet Products")
    db.add(company)
    db.flush()
    product = Product(
        company_id=company.id,
        product_name_cn="宠物凉感垫",
        product_name_en=None,
        category="宠物用品",
        cost_price_cny=Decimal("18.20"),
        weight_kg=Decimal("0.300"),
        package_size="40x30x4cm",
        material="Nylon",
        description="该产品来自用户上传截图/链接，经 AI 提取后由用户确认。",
    )
    db.add(product)
    db.flush()
    job = ProductImportJob(
        company_id=company.id,
        source_type="url",
        source_platform="jd",
        source_url="https://item.jd.com/100012043978.html?token=secret-token",
        status="confirmed",
    )
    db.add(job)
    db.flush()
    db.add(
        ProductDraft(
            import_job_id=job.id,
            company_id=company.id,
            product_name_cn="宠物凉感垫",
            product_name_en=None,
            category="宠物用品",
            package_size="40x30x4cm",
            material="Nylon",
            source_platform="jd",
            source_url="https://item.jd.com/100012043978.html?token=secret-token",
            evidence=[{"field": "product_name_cn", "source": "url_text", "value": "宠物凉感垫"}],
            confidence_score=Decimal("0.4000"),
            status="confirmed",
            confirmed_product_id=product.id,
        )
    )
    db.commit()
    return company.id, product.id
