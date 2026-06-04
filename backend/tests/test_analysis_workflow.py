from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from decimal import Decimal
from time import perf_counter

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models import Company, OpportunityScore, Product, ProductDraft, ProductImportJob, ProductKeyword, Report
from app.schemas import (
    AnalysisRunRequest,
    DataSourceCompetitorItem,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendItem,
    DataSourceContentTrendResponse,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
)
from app.services.agents import ExportInsightWorkflow
from app.services.agents.export_insight_workflow import DataCollectionAgent, WorkflowContext
from app.services.ai import BailianChatCompletion, BailianTimeoutError
from app.services.analysis_performance import (
    AnalysisPerformanceRecorder,
    analysis_performance_scope,
    get_performance_events,
    step_performance_counts,
)
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

    performance = workflow.performance(analysis_run.id)
    assert performance is not None
    assert len(performance.steps) == 9
    assert performance.provider_call_count > 0
    assert performance.qwen_call_count > 0
    assert performance.fallback_count > 0
    assert performance.cache_hit_count > 0
    assert performance.provider_summary
    assert performance.qwen_summary
    assert any(step.step_id == "03_data_collection" and step.provider_call_count > 0 for step in performance.steps)
    assert any(
        step.step_id == "03_data_collection"
        and step.status == "fallback_used"
        and step.fallback_reason == "provider_unavailable"
        for step in status.step_logs
    )
    assert any(
        event.provider == "un_comtrade"
        and event.status == "fallback"
        and event.fallback_reason == "provider_unavailable"
        for event in performance.events
    )
    assert any(step.step_id == "07_opportunity_scoring" and step.provider_call_count > 0 for step in performance.steps)
    assert all(step.provider_call_count >= 0 for step in performance.steps)

    serialized = json.dumps(performance.model_dump(mode="json"), ensure_ascii=False).casefold()
    assert "authorization" not in serialized
    assert "cookie" not in serialized
    assert "api_key" not in serialized
    assert ".env" not in serialized
    assert "secret-token" not in serialized


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


def test_workflow_records_qwen_timeout_count(
    db_session: Session,
) -> None:
    company_id, product_id = _seed_product(db_session)
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=TimeoutAiClient(),
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
    performance = workflow.performance(analysis_run.id)
    assert performance is not None
    assert performance.timeout_count > 0
    assert any(event.type == "qwen" and event.timeout for event in performance.events)
    assert any(step.qwen_call_count > 0 and step.timeout_count > 0 for step in performance.steps)


def test_report_qwen_timeout_uses_fallback_report_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("BAILIAN_TIMEOUT_SECONDS", "0.01")
    get_settings.cache_clear()
    company_id, product_id = _seed_product(db_session)
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=SlowReportAiClient(),
    )
    analysis_run = workflow.create_run(
        AnalysisRunRequest(
            company_id=company_id,
            product_ids=[product_id],
            target_countries=["US"],
            competitor_limit=8,
        )
    )

    try:
        status = asyncio.run(workflow.run(analysis_run.id))
    finally:
        get_settings.cache_clear()

    assert status is not None
    assert status.status == "fallback_used"
    assert status.finished_at is not None
    assert status.current_step == "09_report_prep"
    step = _step_log(status, "09_report_prep")
    assert step.status == "fallback_used"
    assert step.fallback_used is True
    assert step.timeout_count > 0
    assert step.fallback_count > 0
    assert step.output_summary["ai_fallback_used"] is True

    report = db_session.scalar(select(Report).where(Report.analysis_id == analysis_run.id))
    assert report is not None
    assert report.content_markdown is not None
    assert "qwen3.6-plus" in report.content_markdown
    assert report.content_html is not None

    performance = workflow.performance(analysis_run.id)
    assert performance is not None
    assert any(
        event.type == "qwen"
        and event.step_id == "09_report_prep"
        and event.timeout
        and event.fallback_used
        for event in performance.events
    )


def test_report_prep_unrecoverable_error_adds_retry_entry_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    company_id, product_id = _seed_product(db_session)

    async def fail_generate(self: object, analysis_id: int, *, force_regenerate: bool = False) -> object:
        raise RuntimeError("renderer unavailable")

    monkeypatch.setattr(
        "app.services.agents.export_insight_workflow.ReportGenerator.generate_from_analysis",
        fail_generate,
    )
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=BadJsonAiClient(),
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
    assert status.finished_at is not None
    assert status.next_page_url == f"/reports?analysis_id={analysis_run.id}"
    step = _step_log(status, "09_report_prep")
    assert step.status == "fallback_used"
    assert step.fallback_used is True
    assert step.output_summary["retry_available"] is True

    report_count = db_session.scalar(
        select(func.count()).select_from(Report).where(Report.analysis_id == analysis_run.id)
    )
    assert report_count == 0
    refreshed_run = db_session.get(type(analysis_run), analysis_run.id)
    assert refreshed_run is not None
    reports = (refreshed_run.workflow_state or {}).get("reports")
    assert isinstance(reports, list)
    assert reports[-1]["generation_status"] == "retry_available"
    assert reports[-1]["next_page_url"] == f"/reports?analysis_id={analysis_run.id}"


def test_marketing_qwen_timeout_uses_fallback_assets_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("BAILIAN_TIMEOUT_SECONDS", "0.01")
    get_settings.cache_clear()
    company_id, product_id = _seed_product(db_session)
    workflow = ExportInsightWorkflow(
        db_session,
        _failing_data_source_service(db_session),
        ai_client=SlowMarketingAiClient(),
    )
    analysis_run = workflow.create_run(
        AnalysisRunRequest(
            company_id=company_id,
            product_ids=[product_id],
            target_countries=["US"],
            competitor_limit=8,
        )
    )

    try:
        status = asyncio.run(workflow.run(analysis_run.id))
    finally:
        get_settings.cache_clear()

    assert status is not None
    assert status.status == "fallback_used"
    assert status.finished_at is not None
    step = _step_log(status, "08_marketing_prep")
    assert step.status == "fallback_used"
    assert step.fallback_used is True
    assert step.timeout_count > 0
    assert step.fallback_count > 0
    assert step.output_summary["ai_fallback_used"] is True

    refreshed_run = db_session.get(type(analysis_run), analysis_run.id)
    assert refreshed_run is not None
    assets = (refreshed_run.workflow_state or {}).get("marketing_assets")
    assert isinstance(assets, list)
    assert assets
    assert assets[0]["product_id"] == product_id
    assert assets[0]["country"] == "US"
    assert "listing_title" in assets[0]

    performance = workflow.performance(analysis_run.id)
    assert performance is not None
    assert any(
        event.type == "qwen"
        and event.step_id == "08_marketing_prep"
        and event.timeout
        and event.fallback_used
        for event in performance.events
    )


def test_parallel_data_collection_preserves_serial_result_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = _data_collection_profiles()
    countries = ["US", "GB"]
    monkeypatch.setenv("DATA_COLLECTION_CONCURRENCY", "3")
    get_settings.cache_clear()

    parallel_result, _state, _service = asyncio.run(
        _run_data_collection_agent(profiles, countries, StubDataCollectionService())
    )
    serial_state = asyncio.run(_serial_data_collection_reference(profiles, countries))

    assert parallel_result.state_updates is not None
    assert _data_collection_shape(parallel_result.state_updates) == _data_collection_shape(serial_state)
    get_settings.cache_clear()


def test_parallel_data_collection_dedupes_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = [
        _data_collection_profile(1, keyword="same throw", hs_code="630140"),
        _data_collection_profile(2, keyword=" same   throw ", hs_code="630140"),
    ]
    monkeypatch.setenv("DATA_COLLECTION_CONCURRENCY", "3")
    get_settings.cache_clear()

    result, state, service = asyncio.run(_run_data_collection_agent(profiles, ["US"], StubDataCollectionService()))

    assert service.market_calls == ["US"]
    assert service.competitor_calls == [("same throw", "US", 8)]
    assert service.content_calls == [("same throw", "US", 20)]
    assert service.trade_calls == [("Home Textile", "630140", "US")]
    assert result.output_summary["local_cache_hit_count"] == 3
    assert result.output_summary["cache_hit_count"] == 3
    assert step_performance_counts(state, "03_data_collection")["provider_call_count"] == 0
    assert step_performance_counts(state, "03_data_collection")["cache_hit_count"] == 3
    get_settings.cache_clear()


def test_parallel_data_collection_provider_failure_falls_back_without_failed_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATA_COLLECTION_CONCURRENCY", "3")
    get_settings.cache_clear()

    result, state, _service = asyncio.run(
        _run_data_collection_agent(
            [_data_collection_profile(1, keyword="boho throw", hs_code="630140")],
            ["US"],
            StubDataCollectionService(fail_endpoints={"competitors"}),
        )
    )

    assert result.state_updates is not None
    signal = result.state_updates["raw_signals"]["1:US"]
    assert signal["competitors"].fallback_used is True
    assert signal["content"].fallback_used is False
    assert signal["trade"].fallback_used is False
    assert result.fallback_used is True
    assert result.fallback_reason == "provider_unavailable"
    assert result.output_summary["fallback_count"] >= 1
    assert result.output_summary["timeout_count"] == 0
    assert any(
        event.get("provider") == "etsy"
        and event.get("status") == "fallback"
        and event.get("fallback_reason") == "provider_unavailable"
        for event in get_performance_events(state)
    )
    get_settings.cache_clear()


def test_parallel_data_collection_reduces_slow_provider_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles = [
        _data_collection_profile(1, keyword="boho throw", hs_code="630140"),
        _data_collection_profile(2, keyword="cotton bedding", hs_code="630221"),
    ]
    countries = ["US", "GB"]

    monkeypatch.setenv("DATA_COLLECTION_CONCURRENCY", "1")
    get_settings.cache_clear()
    serial_started = perf_counter()
    asyncio.run(_run_data_collection_agent(profiles, countries, StubDataCollectionService(delay_seconds=0.03)))
    serial_duration = perf_counter() - serial_started

    monkeypatch.setenv("DATA_COLLECTION_CONCURRENCY", "3")
    get_settings.cache_clear()
    parallel_started = perf_counter()
    asyncio.run(_run_data_collection_agent(profiles, countries, StubDataCollectionService(delay_seconds=0.03)))
    parallel_duration = perf_counter() - parallel_started

    assert parallel_duration < serial_duration * 0.75
    get_settings.cache_clear()


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


class TimeoutAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        raise BailianTimeoutError("Bailian request timed out.")


class SlowReportAiClient(BadJsonAiClient):
    async def chat(self, messages: list[dict[str, str]], *args: object, **kwargs: object) -> BailianChatCompletion:
        prompt_text = "\n".join(message.get("content", "") for message in messages)
        if "content_markdown" in prompt_text and "required_sections" in prompt_text:
            await asyncio.sleep(0.05)
        return await super().chat(messages, *args, **kwargs)


class SlowMarketingAiClient(BadJsonAiClient):
    async def chat(self, messages: list[dict[str, str]], *args: object, **kwargs: object) -> BailianChatCompletion:
        prompt_text = "\n".join(message.get("content", "") for message in messages)
        if "listing_title" in prompt_text and "localization_notes" in prompt_text:
            await asyncio.sleep(0.05)
        return await super().chat(messages, *args, **kwargs)


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


class StubDataCollectionService:
    def __init__(
        self,
        *,
        delay_seconds: float = 0,
        fail_endpoints: set[str] | None = None,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.fail_endpoints = fail_endpoints or set()
        self.market_calls: list[str] = []
        self.competitor_calls: list[tuple[str, str, int]] = []
        self.content_calls: list[tuple[str, str, int]] = []
        self.trade_calls: list[tuple[str, str, str]] = []

    async def get_market_profile(self, country_code: str) -> WorldBankCountryResponse:
        await self._maybe_delay()
        self._maybe_fail("market")
        country = country_code.strip().upper()
        self.market_calls.append(country)
        return WorldBankCountryResponse(
            country_code=country,
            indicators=[
                WorldBankIndicatorItem(
                    indicator_code="NY.GDP.PCAP.CD",
                    indicator_name="GDP per capita",
                    year=2025,
                    value=50000,
                    source="api",
                )
            ],
            fallback_used=False,
        )

    async def search_competitors(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 20,
    ) -> DataSourceCompetitorSearchResponse:
        await self._maybe_delay()
        self._maybe_fail("competitors")
        normalized_country = (country or "US").strip().upper()
        self.competitor_calls.append((keyword, normalized_country, limit))
        return DataSourceCompetitorSearchResponse(
            keyword=keyword,
            country=normalized_country,
            items=[
                DataSourceCompetitorItem(
                    platform="Etsy",
                    country=normalized_country,
                    keyword=keyword,
                    title=f"{keyword} competitor",
                    price=Decimal("42"),
                    currency="USD",
                    source_type="api",
                )
            ],
            fallback_used=False,
            sources=["Etsy"],
        )

    async def get_content_trends(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 20,
    ) -> DataSourceContentTrendResponse:
        await self._maybe_delay()
        self._maybe_fail("content")
        normalized_country = (country or "US").strip().upper()
        self.content_calls.append((keyword, normalized_country, limit))
        return DataSourceContentTrendResponse(
            keyword=keyword,
            country=normalized_country,
            items=[
                DataSourceContentTrendItem(
                    platform="YouTube",
                    country=normalized_country,
                    keyword=keyword,
                    title=f"{keyword} trend",
                    source_type="api",
                )
            ],
            fallback_used=False,
            sources=["YouTube"],
        )

    async def get_trade_data(
        self,
        product_category: str,
        hs_code: str | None = None,
        country: str | None = None,
    ) -> UnComtradeTradeFlowResponse:
        await self._maybe_delay()
        self._maybe_fail("trade")
        normalized_country = (country or "US").strip().upper()
        normalized_hs_code = (hs_code or "6302").strip().upper()
        self.trade_calls.append((product_category, normalized_hs_code, normalized_country))
        return UnComtradeTradeFlowResponse(
            hs_code=normalized_hs_code,
            reporter="CHN",
            partner=normalized_country,
            flow="export",
            records=[
                UnComtradeTradeRecord(
                    year=2024,
                    trade_value_usd=Decimal("999"),
                    quantity=Decimal("9"),
                    source="api",
                )
            ],
            fallback_used=False,
            auth_mode="no_key",
        )

    async def _maybe_delay(self) -> None:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

    def _maybe_fail(self, endpoint: str) -> None:
        if endpoint in self.fail_endpoints:
            raise RuntimeError(f"{endpoint} unavailable")


async def _run_data_collection_agent(
    profiles: list[dict[str, object]],
    countries: list[str],
    service: StubDataCollectionService,
) -> tuple[object, dict[str, object], StubDataCollectionService]:
    state: dict[str, object] = {"product_profiles": profiles}
    context = WorkflowContext(
        db=None,  # type: ignore[arg-type]
        analysis_run=None,  # type: ignore[arg-type]
        request=AnalysisRunRequest(
            company_id=1,
            product_ids=[int(profile["id"]) for profile in profiles],
            target_countries=countries,
            competitor_limit=8,
        ),
        data_sources=service,  # type: ignore[arg-type]
        ai_client=None,  # type: ignore[arg-type]
        state=state,
    )
    agent = DataCollectionAgent()
    with analysis_performance_scope(AnalysisPerformanceRecorder(state), agent.step.step_id):
        result = await agent.run(context)
    return result, state, service


async def _serial_data_collection_reference(
    profiles: list[dict[str, object]],
    countries: list[str],
) -> dict[str, object]:
    service = StubDataCollectionService()
    market_profiles: dict[str, WorldBankCountryResponse] = {}
    raw_signals: dict[str, dict[str, object]] = {}
    summaries: list[dict[str, object]] = []
    for country in countries:
        market_profiles[country] = await service.get_market_profile(country)
    for product in profiles:
        keyword = str(product.get("keyword") or product.get("product_name_en") or product.get("product_name_cn"))
        category = str(product.get("category") or keyword)
        hs_code = str(product.get("hs_code") or "6302")
        for country in countries:
            competitors = await service.search_competitors(keyword, country=country, limit=8)
            content = await service.get_content_trends(keyword, country=country, limit=20)
            trade = await service.get_trade_data(category, hs_code=hs_code, country=country)
            key = f"{int(product['id'])}:{country.upper()}"
            raw_signals[key] = {
                "product": product,
                "country": country,
                "competitors": competitors,
                "content": content,
                "market": market_profiles[country],
                "trade": trade,
            }
            summaries.append(
                {
                    "product_id": product["id"],
                    "country": country,
                    "competitor_items": len(competitors.items),
                    "content_items": len(content.items),
                    "market_indicators": len(market_profiles[country].indicators),
                    "trade_records": len(trade.records),
                }
            )
    return {"raw_signals": raw_signals, "data_collection_summary": summaries}


def _data_collection_shape(state_updates: dict[str, object]) -> dict[str, object]:
    raw_signals = state_updates["raw_signals"]
    assert isinstance(raw_signals, dict)
    return {
        "raw_signal_keys": list(raw_signals),
        "summaries": state_updates["data_collection_summary"],
        "signals": {
            key: {
                "product_id": signal["product"]["id"],
                "country": signal["country"],
                "competitor_items": len(signal["competitors"].items),
                "content_items": len(signal["content"].items),
                "market_indicators": len(signal["market"].indicators),
                "trade_records": len(signal["trade"].records),
            }
            for key, signal in raw_signals.items()
        },
    }


def _data_collection_profiles() -> list[dict[str, object]]:
    return [
        _data_collection_profile(1, keyword="boho throw", hs_code="630140"),
        _data_collection_profile(2, keyword="cotton bedding", hs_code="630221"),
    ]


def _data_collection_profile(product_id: int, *, keyword: str, hs_code: str) -> dict[str, object]:
    return {
        "id": product_id,
        "product_name_cn": f"Product {product_id}",
        "product_name_en": keyword.title(),
        "category": "Home Textile",
        "keyword": keyword,
        "hs_code": hs_code,
    }


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


def _step_log(status: object, step_id: str) -> object:
    return next(step for step in status.step_logs if step.step_id == step_id)


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
