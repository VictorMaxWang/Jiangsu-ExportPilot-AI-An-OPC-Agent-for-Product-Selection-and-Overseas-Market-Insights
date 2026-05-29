from __future__ import annotations

import json
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AnalysisRun, Company, OpportunityScore, Product, ProductDraft, ProductImportJob, Report
from app.services.ai import BailianChatCompletion, BailianConfigurationError
from app.services.reports import REPORT_SECTION_TITLES, REPORT_TITLE


def test_report_generate_saves_markdown_html_and_routes(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_report_analysis(session_factory)
    stub = StubBailianClient(json.dumps({"content_markdown": _valid_report_markdown()}))
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == REPORT_TITLE
    assert "## 3. 数据源说明" in payload["content_markdown"]
    assert "<article" in payload["content_html"]
    assert "Authorization" not in response.text
    assert "Bearer" not in response.text
    assert "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。" in payload["content_markdown"]
    assert "国内商品截图/链接用于识别企业可供产品信息。" in payload["content_markdown"]
    assert "海外机会评分仍基于海外竞品样本、内容趋势、国家市场画像与贸易数据。" in payload["content_markdown"]
    assert "国内链接价格不代表海外销售价格" in payload["content_markdown"]
    assert "来源平台 jd" in payload["content_markdown"]
    assert "https://item.jd.com/100012043978.html" in payload["content_markdown"]
    assert "证据摘录" in payload["content_markdown"]
    assert "secret-token" not in payload["content_markdown"]
    assert "销量预测" not in payload["content_markdown"]
    assert "GMV" not in payload["content_markdown"]
    assert stub.json_mode is True

    list_response = client.get(f"/api/reports?analysis_id={analysis_id}")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    report_id = payload["id"]
    get_response = client.get(f"/api/reports/{report_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == report_id

    markdown_download = client.get(f"/api/reports/{report_id}/download?format=markdown")
    assert markdown_download.status_code == 200
    assert REPORT_TITLE in markdown_download.text
    assert "text/markdown" in markdown_download.headers["content-type"]

    html_download = client.get(f"/api/reports/{report_id}/download?format=html")
    assert html_download.status_code == 200
    assert "<article" in html_download.text

    pdf_download = client.get(f"/api/reports/{report_id}/download?format=pdf")
    assert pdf_download.status_code == 501

    with session_factory() as db:
        report = db.scalar(select(Report).where(Report.analysis_id == analysis_id))
        assert report is not None
        assert report.content_markdown
        assert report.content_html


def test_report_generate_bad_json_uses_deterministic_fallback(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    analysis_id = _seed_report_analysis(client_with_session[1])
    stub = StubBailianClient("not json")
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    markdown = response.json()["content_markdown"]
    assert REPORT_TITLE in markdown
    assert "## 13. 下一步行动计划" in markdown
    assert "qwen3.6-plus 未返回可用" in markdown
    assert "数据源说明" in markdown


def test_report_generate_missing_key_uses_deterministic_fallback(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_report_analysis(session_factory)
    app.dependency_overrides[get_bailian_client] = lambda: MissingKeyClient()
    try:
        response = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    response_text = response.text
    assert "BAILIAN_API_KEY" not in response_text
    assert "DASHSCOPE_API_KEY" not in response_text
    assert "Authorization" not in response_text
    assert "Bearer" not in response_text
    assert "## 3. 数据源说明" in response.json()["content_markdown"]


def test_report_generate_rejects_forbidden_ai_claims(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_report_analysis(session_factory)
    unsafe_markdown = _valid_report_markdown(extra_line="- 本产品存在 GMV 和销量预测机会。")
    stub = StubBailianClient(json.dumps({"content_markdown": unsafe_markdown}))
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    markdown = response.json()["content_markdown"]
    assert "GMV" not in markdown
    assert "销量预测" not in markdown
    assert "qwen3.6-plus 未返回可用" in markdown


def test_report_generate_returns_existing_without_force(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_report_analysis(session_factory)
    stub = StubBailianClient(json.dumps({"content_markdown": _valid_report_markdown()}))
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        first = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
        second = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
        third = client.post(
            "/api/reports/generate",
            json={"analysis_id": analysis_id, "force_regenerate": True},
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert third.json()["id"] != first.json()["id"]


@pytest.fixture()
def client_with_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, testing_session_local
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_bailian_client, None)
    Base.metadata.drop_all(bind=engine)


class StubBailianClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, str]] = []
        self.json_mode = False

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> BailianChatCompletion:
        self.messages = messages
        self.json_mode = json_mode
        return BailianChatCompletion(content=self.content, model="qwen3.6-plus")


class MissingKeyClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        raise BailianConfigurationError("Bailian API key is not configured on backend.")


def _seed_report_analysis(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        company = Company(
            name="Nantong Home Textile Co",
            region="Jiangsu Nantong",
            industry="Home Textile",
            description="Export-oriented bedding and throw blanket manufacturer.",
            target_countries=["US", "JP"],
        )
        db.add(company)
        db.flush()
        product = Product(
            company_id=company.id,
            product_name_cn="样本盖毯",
            product_name_en="Boho Throw Blanket",
            category="Home Textile",
            cost_price_cny=Decimal("42.00"),
            weight_kg=Decimal("0.900"),
            package_size="35x28x12cm",
            material="Acrylic cotton blend",
            certification="OEKO-TEX",
            moq=120,
            description="Soft throw blanket for sofa bedroom and gift sets.",
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
                product_name_cn=product.product_name_cn,
                product_name_en=product.product_name_en,
                category=product.category,
                source_platform="jd",
                source_url="https://item.jd.com/100012043978.html?token=secret-token",
                evidence=[{"field": "product_name_cn", "source": "url_text", "value": "样本盖毯"}],
                confidence_score=Decimal("0.6200"),
                status="confirmed",
                confirmed_product_id=product.id,
            )
        )
        analysis_run = AnalysisRun(
            company_id=company.id,
            status="fallback_used",
            input_products=[
                {
                    "id": product.id,
                    "product_name_cn": product.product_name_cn,
                    "product_name_en": product.product_name_en,
                    "category": product.category,
                }
            ],
            target_countries=["US", "JP"],
            step_logs=[
                {
                    "step_id": "03_data_collection",
                    "node": "DataCollectionAgent",
                    "title": "Data collection",
                    "status": "fallback_used",
                    "sources": [
                        {
                            "provider": "un_comtrade",
                            "source_label": "CSV fallback: trade_samples.csv",
                            "source_type": "csv_fallback",
                            "fallback_used": True,
                            "api_invoked": False,
                            "detail": "Trade data fallback sample.",
                        }
                    ],
                }
            ],
            workflow_state={
                "product_profiles": [
                    {"id": product.id, "keyword": "boho throw blanket", "hs_code": "630140"}
                ],
                "market_profiles": [
                    {
                        "product_id": product.id,
                        "country": "US",
                        "summary": "US shows directional demand for home textile sample products.",
                        "market_size_score": 86,
                        "trade_score": 78,
                        "logistics_score": 72,
                        "competition_level": "medium",
                    }
                ],
                "content_trends": [
                    {
                        "product_id": product.id,
                        "country": "US",
                        "keyword": "boho throw blanket",
                        "content_themes": ["giftable home textile"],
                        "marketing_angles": ["room refresh"],
                        "pain_points": ["Buyers need clear material and care details."],
                        "source_item_count": 6,
                    }
                ],
                "marketing_assets": [
                    {
                        "product_id": product.id,
                        "country": "US",
                        "title": "Boho Throw Blanket for Cozy Apartment Styling",
                        "bullet_points": [
                            "Soft acrylic cotton blend for sofa and bedroom styling.",
                            "Boho texture supports neutral room refreshes.",
                            "Lightweight throw format supports practical shipping.",
                            "Clear material and care details support comparison.",
                            "Lifestyle photos should show scale and texture.",
                        ],
                        "short_video_script": "Show a room refresh, texture closeups, and care details.",
                        "pinterest_keywords": ["boho bedroom throw"],
                        "platform_listing_advice": "Publish as a draft after human review.",
                        "risk_notes": ["Sample data analysis only."],
                    }
                ],
                "provider_sources": [
                    {
                        "provider": "worldbank",
                        "source_label": "World Bank API",
                        "source_type": "api",
                        "fallback_used": False,
                        "api_invoked": True,
                        "detail": "Macroeconomic indicators.",
                    }
                ],
            },
        )
        db.add(analysis_run)
        db.flush()
        db.add(
            OpportunityScore(
                analysis_id=analysis_run.id,
                product_id=product.id,
                country="US",
                trend_score=Decimal("81.00"),
                price_score=Decimal("77.00"),
                market_score=Decimal("84.00"),
                supply_score=Decimal("88.00"),
                logistics_score=Decimal("72.00"),
                content_score=Decimal("69.00"),
                total_score=Decimal("82.50"),
                rank=1,
                reason="Structured signals support a cautious entry test.",
                risk="Validate certification and price band before paid launch.",
                next_action="Run a small localized listing test with conservative claims.",
                fallback_used=True,
                ai_fallback_used=False,
                sources=[
                    {
                        "provider": "etsy",
                        "source_label": "CSV fallback: competitor_samples.csv",
                        "source_type": "csv_fallback",
                        "fallback_used": True,
                        "api_invoked": False,
                        "detail": "Competitor sample rows are price signals only.",
                    }
                ],
                evidence={"keyword": "boho throw blanket", "content_fallback_used": True},
                competitor_analysis={
                    "keyword": "boho throw blanket",
                    "country": "US",
                    "item_count": 12,
                    "min_price": "12.00",
                    "median_price": "24.00",
                    "avg_price": "25.50",
                    "max_price": "42.00",
                    "currency": "USD",
                    "competition_level": "medium",
                    "price_suggestion": "Use USD 18-24 for an entry test band.",
                    "summary": "Competitor sample rows show a directional price band.",
                },
            )
        )
        db.commit()
        return analysis_run.id


def _valid_report_markdown(*, extra_line: str = "") -> str:
    lines = [
        f"# {REPORT_TITLE}",
        "> Report generated from structured data. Competitor samples do not represent real sales.",
    ]
    for index, section_title in enumerate(REPORT_SECTION_TITLES, start=1):
        lines.append(f"## {index}. {section_title}")
        lines.append(f"- {section_title} uses structured analysis evidence only.")
        if index == 3:
            lines.append("- Data source notes include API, sample, and fallback labels.")
        if extra_line and index == 5:
            lines.append(extra_line)
    return "\n\n".join(lines)
