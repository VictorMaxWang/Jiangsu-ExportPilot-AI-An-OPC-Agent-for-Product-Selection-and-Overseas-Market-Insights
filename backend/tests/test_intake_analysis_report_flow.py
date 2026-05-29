from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.api.analysis import get_analysis_background_runner
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import Product, ProductDraft, ProductKeyword
from app.services.agents import ExportInsightWorkflow
from app.services.ai import BailianChatCompletion
from app.services.data_sources import DataSourceService
from app.services.product_intake.domestic_page_fetcher import DomesticPageFetchInput, DomesticPageFetchResult


URL_INTAKE_PAYLOAD: dict[str, object] = {
    "source_platform": "jd",
    "product_name_cn": "端到端宠物凉感垫",
    "product_name_en": None,
    "category": "Pet supplies",
    "price_cny": 39.9,
    "material": "尼龙",
    "specification": "夏季宠物凉感垫",
    "dimensions": "28x18x4cm",
    "weight_estimate": "0.45kg",
    "color_options": ["蓝色"],
    "selling_points_cn": ["夏季降温"],
    "selling_points_en": ["Cooling mat for summer"],
    "target_users": ["pet owners"],
    "usage_scenarios": ["home"],
    "cross_border_keywords_en": [],
    "risk_notes": ["URL text is public page text and requires manual review."],
    "confidence_score": 0.62,
    "evidence": [
        {"field": "product_name_cn", "source": "url_text", "value": "端到端宠物凉感垫"},
        {"field": "price_cny", "source": "url_text", "value": "参考价 39.90"},
    ],
}


@pytest.fixture()
def client_with_session(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker[Session], "Q15FlowAiClient"], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    ai_client = Q15FlowAiClient()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_background_runner() -> Callable[[int], Awaitable[None]]:
        async def runner(analysis_id: int) -> None:
            db = testing_session_local()
            try:
                workflow = ExportInsightWorkflow(
                    db,
                    _failing_data_source_service(db),
                    ai_client=ai_client,
                )
                await workflow.run(analysis_id)
            finally:
                db.close()

        return runner

    monkeypatch.setenv("ENABLE_DOMESTIC_URL_FETCH", "true")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-key")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.product_intake.url_intake.fetch_domestic_product_page", FakePageFetcher())

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_bailian_client] = lambda: ai_client
    app.dependency_overrides[get_analysis_background_runner] = override_background_runner
    with TestClient(app) as test_client:
        yield test_client, testing_session_local, ai_client
    app.dependency_overrides.pop(get_analysis_background_runner, None)
    app.dependency_overrides.pop(get_bailian_client, None)
    app.dependency_overrides.pop(get_db, None)
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)


def test_intake_confirm_analysis_dashboard_report_flow(
    client_with_session: tuple[TestClient, sessionmaker[Session], "Q15FlowAiClient"],
) -> None:
    client, session_factory, ai_client = client_with_session
    company = client.post(
        "/api/companies",
        json={
            "name": "Q15 E2E Home Goods",
            "region": "Jiangsu",
            "industry": "Pet supplies",
            "description": "End-to-end product intake analysis company.",
            "target_countries": ["US"],
        },
    )
    assert company.status_code == 201
    company_id = int(company.json()["id"])

    intake = client.post(
        "/api/product-intake/url",
        json={"company_id": company_id, "url": "https://item.jd.com/100012043978.html?token=secret-token"},
    )
    assert intake.status_code == 201
    intake_payload = intake.json()
    assert intake_payload["draft"]["low_confidence"] is True
    assert "secret-token" not in intake.text

    confirm = client.post(
        f"/api/product-intake/drafts/{intake_payload['draft_id']}/confirm",
        json={"company_id": company_id},
    )
    assert confirm.status_code == 200
    product_id = int(confirm.json()["id"])
    assert confirm.json()["product_name_en"] is None
    assert "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。" in confirm.json()["description"]
    assert "非采购成本" in confirm.json()["description"]

    with session_factory() as db:
        product = db.get(Product, product_id)
        draft = db.get(ProductDraft, int(intake_payload["draft_id"]))
        assert product is not None and product.product_name_en is None
        assert draft is not None and draft.confirmed_product_id == product_id and draft.status == "confirmed"
        assert db.scalar(select(func.count()).select_from(ProductKeyword)) == 0

    start = client.post(
        "/api/analysis/run",
        json={"company_id": company_id, "product_ids": [product_id], "target_countries": ["US"], "competitor_limit": 8},
    )
    assert start.status_code == 202
    analysis_id = int(start.json()["analysis_id"])

    status = client.get(f"/api/analysis/{analysis_id}/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["status"] in {"success", "fallback_used"}
    assert status_payload["current_step"] == "09_report_prep"
    assert status_payload["scoring_summary"]["item_count"] == 1

    detail = client.get(f"/api/analysis/{analysis_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["scores"]
    assert detail_payload["marketing_assets"]
    assert len(detail_payload["reports"]) == 1
    profile = detail_payload["workflow_state"]["product_profiles"][0]
    assert profile["keyword_source"] == "bailian_generated"
    assert profile["product_keywords"] == ["pet cooling mat", "summer pet mat"]
    assert profile["intake_source"]["source_url"] == "https://item.jd.com/100012043978.html"
    assert profile["intake_source"]["domestic_price_role"] == "domestic_reference_only"
    score = detail_payload["scores"][0]
    assert score["price_score"] == "45.00"
    assert score["evidence"]["intake_source"]["domestic_reference_price_cny"] == "39.90"
    assert "secret-token" not in json.dumps(detail_payload, ensure_ascii=False)

    dashboard = client.get(f"/api/dashboard/{analysis_id}")
    assert dashboard.status_code == 200
    dashboard_payload = dashboard.json()
    assert dashboard_payload["product_scores"]
    assert dashboard_payload["price_ranges"]

    report = client.post("/api/reports/generate", json={"analysis_id": analysis_id})
    assert report.status_code == 200
    markdown = report.json()["content_markdown"]
    assert "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。" in markdown
    assert "国内商品截图/链接用于识别企业可供产品信息。" in markdown
    assert "海外机会评分仍基于海外竞品样本、内容趋势、国家市场画像与贸易数据。" in markdown
    assert "国内链接价格不代表海外销售价格" in markdown
    assert "https://item.jd.com/100012043978.html" in markdown
    assert "secret-token" not in markdown
    assert ai_client.keyword_calls == 1


class Q15FlowAiClient:
    def __init__(self) -> None:
        self.keyword_calls = 0

    async def chat(self, messages: list[dict[str, str]], *args: object, **kwargs: object) -> BailianChatCompletion:
        prompt_text = "\n".join(message.get("content", "") for message in messages)
        if "cross_border_keywords_en" in prompt_text and "confidence_score" in prompt_text:
            return BailianChatCompletion(content=json.dumps(URL_INTAKE_PAYLOAD, ensure_ascii=False), model="qwen3.6-plus")
        if "keywords_en" in prompt_text and "product_name_en" in prompt_text:
            self.keyword_calls += 1
            return BailianChatCompletion(
                content=json.dumps(
                    {
                        "product_name_en": "Pet Cooling Mat",
                        "keywords_en": ["pet cooling mat", "summer pet mat"],
                        "keywords_jp": ["ペット冷感マット"],
                        "target_users": ["Pet owners"],
                        "selling_points": ["Cool-touch mat for summer pet care"],
                        "risk_notes": ["Verify material and safety claims before launch."],
                    },
                    ensure_ascii=False,
                ),
                model="qwen3.6-plus",
            )
        if "content_markdown" in prompt_text:
            return BailianChatCompletion(content=json.dumps({"content_markdown": _valid_report_markdown()}), model="qwen3.6-plus")
        return BailianChatCompletion(
            content=json.dumps(
                {
                    "reason": "Backend scores show directional opportunity based on overseas evidence.",
                    "risk": "Validate live competitor samples before paid launch.",
                    "next_action": "Run a conservative listing test with localized content.",
                }
            ),
            model="qwen3.6-plus",
        )


class FakePageFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, parsed: DomesticPageFetchInput) -> DomesticPageFetchResult:
        self.calls.append(parsed.normalized_url)
        return DomesticPageFetchResult(
            parse_status="parsed",
            title="端到端宠物凉感垫 - 京东",
            meta_description="夏季宠物凉感垫，参考价￥39.90",
            og_title="端到端宠物凉感垫",
            og_image="https://img.example.com/product.jpg",
            visible_text="端到端宠物凉感垫 夏季降温 尼龙材质 参考价￥39.90",
            price_candidates=["参考价￥39.90"],
            product_name_candidates=["端到端宠物凉感垫"],
            http_status=200,
            final_url="https://item.jd.com/100012043978.html",
            message="parsed",
        )


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


def _failing_data_source_service(db: Session) -> DataSourceService:
    return DataSourceService(
        db,
        worldbank_provider=FailingWorldBankProvider(),
        un_comtrade_provider=FailingUnComtradeProvider(),
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
        etsy_provider=FailingEtsyProvider(),
    )


def _valid_report_markdown() -> str:
    lines = ["# 《南通家纺企业海外市场出海选品洞察报告》"]
    section_titles = [
        "企业画像",
        "产品清单",
        "数据源说明",
        "目标国家市场概览",
        "产品机会评分排名",
        "竞品价格区间",
        "内容趋势与用户痛点",
        "推荐产品与推荐理由",
        "定价建议",
        "英文标题与五点描述",
        "短视频与社媒内容建议",
        "风险提示",
        "下一步行动计划",
    ]
    for index, section_title in enumerate(section_titles, start=1):
        lines.append(f"## {index}. {section_title}")
        lines.append(f"- {section_title} uses structured analysis evidence only.")
    return "\n".join(lines)
