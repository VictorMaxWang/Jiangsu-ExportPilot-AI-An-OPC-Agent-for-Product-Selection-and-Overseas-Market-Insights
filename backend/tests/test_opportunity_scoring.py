import asyncio
import json
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ApiCallLog, AnalysisRun, Company, Product, ProductDraft, ProductImportJob
from app.schemas import (
    DataSourceCompetitorItem,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendItem,
    DataSourceContentTrendResponse,
    ScoringRunRequest,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
)
from app.services.ai import BailianChatCompletion, BailianConfigurationError
from app.services.data_sources import DataSourceService
from app.services.scoring import OpportunityScoringService


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

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


def test_total_score_is_clamped_0_100(db_session: Session) -> None:
    product = _create_product(db_session)
    service = _service(db_session, ai_client=BadJsonAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US"],
            )
        )
    )

    item = result.items[0]
    for score in (
        item.trend_score,
        item.price_score,
        item.market_score,
        item.supply_score,
        item.logistics_score,
        item.content_score,
        item.total_score,
    ):
        assert Decimal("0") <= score <= Decimal("100")


def test_etsy_fallback_still_produces_score(db_session: Session) -> None:
    product = _create_product(db_session)
    service = _service(db_session, ai_client=BadJsonAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US"],
            )
        )
    )

    item = result.items[0]
    assert item.fallback_used is True
    assert item.total_score > 0
    assert item.competitor_analysis.item_count > 0
    assert any(source.provider == "etsy" and source.source_type == "csv_fallback" for source in item.sources)
    providers = set(db_session.scalars(select(ApiCallLog.provider)))
    assert "ebay" not in providers


def test_light_small_product_gets_higher_logistics_score(db_session: Session) -> None:
    company = _create_company(db_session)
    light = _create_product(
        db_session,
        company=company,
        name_en="Boho Throw Blanket",
        weight_kg=Decimal("0.30"),
        package_size="18x14x4cm",
    )
    heavy = _create_product(
        db_session,
        company=company,
        name_en="Boho Throw Blanket",
        weight_kg=Decimal("8.00"),
        package_size="100x80x50cm",
    )
    service = _service(db_session, ai_client=BadJsonAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=company.id,
                product_ids=[light.id, heavy.id],
                target_countries=["US"],
            )
        )
    )

    by_product = {item.product_id: item for item in result.items}
    assert by_product[light.id].logistics_score > by_product[heavy.id].logistics_score


def test_too_low_price_adds_risk_note(db_session: Session) -> None:
    product = _create_product(db_session, cost_price_cny=Decimal("1.00"))
    service = _service(db_session, ai_client=ValidAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US"],
            )
        )
    )

    assert "far below the competitor band" in result.items[0].risk


def test_default_scoring_uses_deterministic_explanation_without_qwen(db_session: Session) -> None:
    product = _create_product(db_session)
    service = _service(db_session, ai_client=ScoreInjectingAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US"],
            )
        )
    )

    item = result.items[0]
    assert item.total_score != Decimal("999.00")
    assert item.ai_fallback_used is False
    assert item.reason != "Injected reason"
    assert item.reason


def test_scoring_reuses_raw_signals_and_does_not_call_qwen_per_row(db_session: Session) -> None:
    product = _create_product(db_session)
    analysis_run = AnalysisRun(
        company_id=product.company_id,
        status="running",
        input_products=[],
        target_countries=["US", "JP"],
    )
    db_session.add(analysis_run)
    db_session.commit()
    db_session.refresh(analysis_run)
    ai_client = CountingAiClient()
    service = _service(db_session, ai_client=ai_client)
    raw_signals = {
        f"{product.id}:US": _raw_signal(product, "US"),
        f"{product.id}:JP": _raw_signal(product, "JP"),
    }

    result = asyncio.run(
        service.run_for_analysis(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US", "JP"],
                competitor_limit=20,
            ),
            analysis_run=analysis_run,
            final_status=None,
            raw_signals=raw_signals,
            use_ai_explanations=False,
        )
    )

    assert result.item_count == 2
    assert all(item.total_score > 0 for item in result.items)
    assert all(item.ai_fallback_used is False for item in result.items)
    assert ai_client.calls == 0
    assert list(db_session.scalars(select(ApiCallLog.provider))) == []


def test_ai_failure_keeps_rule_scores_and_uses_deterministic_explanation(db_session: Session) -> None:
    product = _create_product(db_session)
    service = _service(db_session, ai_client=FailingAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=product.company_id,
                product_ids=[product.id],
                target_countries=["US"],
            )
        )
    )

    item = result.items[0]
    assert item.total_score > 0
    assert item.ai_fallback_used is False
    assert item.reason
    assert item.next_action


def test_domestic_reference_price_does_not_affect_overseas_price_score(db_session: Session) -> None:
    company = _create_company(db_session)
    domestic_reference_product = _create_product(
        db_session,
        company=company,
        name_en="Pet Cooling Mat",
        cost_price_cny=None,
        weight_kg=Decimal("0.45"),
        package_size="28x18x4cm",
    )
    comparison_product = _create_product(
        db_session,
        company=company,
        name_en="Pet Cooling Mat",
        cost_price_cny=None,
        weight_kg=Decimal("0.45"),
        package_size="28x18x4cm",
    )
    _attach_confirmed_domestic_draft(
        db_session,
        product=domestic_reference_product,
        price_cny=Decimal("39.90"),
    )
    service = _service(db_session, ai_client=BadJsonAiClient())

    result = asyncio.run(
        service.run(
            ScoringRunRequest(
                company_id=company.id,
                product_ids=[domestic_reference_product.id, comparison_product.id],
                target_countries=["US"],
            )
        )
    )

    by_product = {item.product_id: item for item in result.items}
    imported_item = by_product[domestic_reference_product.id]
    comparison_item = by_product[comparison_product.id]
    assert imported_item.price_score == Decimal("45.00")
    assert comparison_item.price_score == Decimal("45.00")
    assert imported_item.supply_score - comparison_item.supply_score == Decimal("3.00")
    assert imported_item.evidence["intake_source"]["domestic_reference_price_cny"] == "39.90"
    assert imported_item.evidence["intake_source"]["domestic_price_role"] == "domestic_reference_only"
    assert "不作为海外竞品价格、海外销售价格或采购成本" in imported_item.evidence["intake_source"]["pricing_boundary_note"]


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


class FailingAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        raise BailianConfigurationError("Bailian API key is not configured on backend.")


class ValidAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        return BailianChatCompletion(
            content=json.dumps(
                {
                    "reason": "AI explanation based on backend scores.",
                    "risk": "AI risk text.",
                    "next_action": "AI next action.",
                }
            ),
            model="qwen3.6-plus",
        )


class ScoreInjectingAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        return BailianChatCompletion(
            content=json.dumps(
                {
                    "reason": "Injected reason",
                    "risk": "Injected risk",
                    "next_action": "Injected action",
                    "total_score": 999,
                }
            ),
            model="qwen3.6-plus",
        )


class CountingAiClient:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        self.calls += 1
        return BailianChatCompletion(content="{}", model="qwen3.6-plus")


def _service(db: Session, *, ai_client: object) -> OpportunityScoringService:
    data_sources = DataSourceService(
        db,
        worldbank_provider=FailingWorldBankProvider(),
        un_comtrade_provider=FailingUnComtradeProvider(),
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
        etsy_provider=FailingEtsyProvider(),
    )
    return OpportunityScoringService(db, data_sources, ai_client=ai_client)


def _raw_signal(product: Product, country: str) -> dict[str, object]:
    keyword = product.product_name_en or product.product_name_cn
    return {
        "product": {
            "id": product.id,
            "product_name_cn": product.product_name_cn,
            "product_name_en": product.product_name_en,
            "category": product.category,
            "keyword": keyword,
            "hs_code": "630140",
        },
        "country": country,
        "competitors": DataSourceCompetitorSearchResponse(
            keyword=keyword,
            country=country,
            items=[
                DataSourceCompetitorItem(
                    platform="Etsy",
                    country=country,
                    keyword=keyword,
                    title=f"{keyword} competitor",
                    price=Decimal("45"),
                    currency="USD" if country == "US" else "JPY",
                    source_type="api",
                )
            ],
            fallback_used=False,
            sources=["Etsy"],
        ),
        "content": DataSourceContentTrendResponse(
            keyword=keyword,
            country=country,
            items=[
                DataSourceContentTrendItem(
                    platform="YouTube",
                    country=country,
                    keyword=keyword,
                    title=f"{keyword} styling",
                    heat_score=Decimal("72"),
                    source_type="api",
                )
            ],
            fallback_used=False,
            sources=["YouTube"],
        ),
        "market": WorldBankCountryResponse(
            country_code=country,
            indicators=[
                WorldBankIndicatorItem(
                    indicator_code="NY.GDP.PCAP.CD",
                    indicator_name="GDP per capita",
                    year=2025,
                    value=55000,
                    source="api",
                ),
                WorldBankIndicatorItem(
                    indicator_code="SP.POP.TOTL",
                    indicator_name="Population",
                    year=2025,
                    value=100000000,
                    source="api",
                ),
                WorldBankIndicatorItem(
                    indicator_code="IT.NET.USER.ZS",
                    indicator_name="Internet users",
                    year=2025,
                    value=90,
                    source="api",
                ),
            ],
            fallback_used=False,
        ),
        "trade": UnComtradeTradeFlowResponse(
            hs_code="630140",
            reporter="CHN",
            partner=country,
            flow="export",
            records=[
                UnComtradeTradeRecord(
                    year=2024,
                    trade_value_usd=Decimal("100000000"),
                    quantity=Decimal("1000"),
                    source="api",
                )
            ],
            fallback_used=False,
            auth_mode="no_key",
        ),
    }


def _create_company(db: Session) -> Company:
    company = Company(name="Jiangsu Demo Co", region="Jiangsu", industry="Home Textile")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _create_product(
    db: Session,
    *,
    company: Company | None = None,
    name_en: str = "Boho Throw Blanket",
    cost_price_cny: Decimal | None = Decimal("42.00"),
    weight_kg: Decimal = Decimal("0.90"),
    package_size: str = "35x28x12cm",
) -> Product:
    owner = company or _create_company(db)
    product = Product(
        company_id=owner.id,
        product_name_cn="Boho blanket sample",
        product_name_en=name_en,
        category="Home Textile",
        cost_price_cny=cost_price_cny,
        weight_kg=weight_kg,
        package_size=package_size,
        material="Acrylic cotton blend",
        certification="OEKO-TEX",
        moq=120,
        description="Soft bohemian style throw blanket for sofa bedroom and gift sets",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _attach_confirmed_domestic_draft(
    db: Session,
    *,
    product: Product,
    price_cny: Decimal,
) -> None:
    job = ProductImportJob(
        company_id=product.company_id,
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
            company_id=product.company_id,
            product_name_cn=product.product_name_cn,
            product_name_en=product.product_name_en,
            category=product.category,
            price_cny=price_cny,
            cost_price_cny=None,
            package_size=product.package_size,
            material=product.material,
            source_platform="jd",
            source_url="https://item.jd.com/100012043978.html?token=secret-token",
            evidence=[{"field": "price_cny", "source": "url_text", "value": f"参考价 {price_cny}"}],
            confidence_score=Decimal("0.8200"),
            status="confirmed",
            confirmed_product_id=product.id,
        )
    )
    db.commit()
