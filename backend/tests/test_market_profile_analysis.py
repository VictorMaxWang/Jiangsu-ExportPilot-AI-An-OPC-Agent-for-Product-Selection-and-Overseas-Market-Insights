import asyncio
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.markets import get_market_profile_analysis_service
from app.db.base import Base
from app.main import app
from app.schemas import AnalysisSource, MarketCompareResponse, MarketProfileAnalysisResponse, SuitableProductItem
from app.services.ai import BailianConfigurationError
from app.services.analysis import MarketProfileAnalysisService
from app.services.data_sources import DataSourceService


TARGET_COUNTRIES = ("US", "GB", "JP", "AU", "SG")


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


@pytest.mark.parametrize("country_code", TARGET_COUNTRIES)
def test_target_country_profiles_fallback_to_seed_data(country_code: str, db_session: Session) -> None:
    service = _analysis_service(db_session)

    result = asyncio.run(
        service.analyze_country(
            country_code,
            "home textile",
            keyword="home decor",
            hs_code="6302",
        )
    )

    assert result.country_code == country_code
    assert result.ai_fallback_used is True
    assert result.fallback_used is True
    assert result.suitable_products
    assert result.summary
    for score in (
        result.market_size_score,
        result.consumption_power_score,
        result.internet_score,
        result.trade_score,
        result.logistics_score,
    ):
        assert 0 <= score <= 100
    assert {"worldbank", "un_comtrade", "csv_seed", "bailian"} <= {source.provider for source in result.sources}


def test_compare_defaults_to_five_target_countries_and_sorts(db_session: Session) -> None:
    service = _analysis_service(db_session)

    result = asyncio.run(service.compare_markets("home textile", keyword="home decor"))

    assert result.provider == "market_profile_analysis"
    assert [item.country_code for item in result.items]
    assert {item.country_code for item in result.items} == set(TARGET_COUNTRIES)
    sort_scores = [_sort_score(item) for item in result.items]
    assert sort_scores == sorted(sort_scores, reverse=True)


def test_market_api_routes_map_to_analysis_service() -> None:
    stub = StubMarketProfileAnalysisService()
    app.dependency_overrides[get_market_profile_analysis_service] = lambda: stub
    try:
        with TestClient(app) as client:
            profile = client.get(
                "/api/markets/US/profile",
                params={"product_category": "home textile", "keyword": "home decor", "hs_code": "6302"},
            )
            compare = client.post(
                "/api/markets/compare",
                json={
                    "product_category": "home textile",
                    "country_codes": ["US", "GB"],
                    "keyword": "home decor",
                    "hs_code": "6302",
                },
            )
    finally:
        app.dependency_overrides.pop(get_market_profile_analysis_service, None)

    assert profile.status_code == 200
    assert profile.json()["country_code"] == "US"
    assert compare.status_code == 200
    assert [item["country_code"] for item in compare.json()["items"]] == ["US", "GB"]
    assert stub.calls == [
        ("analyze_country", "US", "home textile", "home decor", "6302"),
        ("compare_markets", "home textile", ["US", "GB"], "home decor", "6302"),
    ]


class FailingWorldBankProvider:
    async def fetch_country(self, _country_code: str) -> object:
        raise RuntimeError("worldbank unavailable")


class FailingUnComtradeProvider:
    async def get_trade_flow(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("un comtrade unavailable")


class FailingAiClient:
    async def chat(self, *args: object, **kwargs: object) -> object:
        raise BailianConfigurationError("Bailian API key is not configured on backend.")


class StubMarketProfileAnalysisService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def analyze_country(
        self,
        country_code: str,
        product_category: str,
        *,
        keyword: str | None = None,
        hs_code: str | None = None,
    ) -> MarketProfileAnalysisResponse:
        self.calls.append(("analyze_country", country_code, product_category, keyword, hs_code))
        return _profile(country_code, product_category, keyword, hs_code)

    async def compare_markets(
        self,
        product_category: str,
        *,
        country_codes: list[str] | None = None,
        keyword: str | None = None,
        hs_code: str | None = None,
    ) -> MarketCompareResponse:
        self.calls.append(("compare_markets", product_category, country_codes, keyword, hs_code))
        items = [_profile(country, product_category, keyword, hs_code) for country in (country_codes or ["US", "GB"])]
        return MarketCompareResponse(
            product_category=product_category,
            keyword=keyword,
            hs_code=hs_code,
            items=items,
            fallback_used=True,
            ai_fallback_used=True,
            sources=items[0].sources,
        )


def _analysis_service(db: Session) -> MarketProfileAnalysisService:
    data_sources = DataSourceService(
        db,
        worldbank_provider=FailingWorldBankProvider(),
        un_comtrade_provider=FailingUnComtradeProvider(),
    )
    return MarketProfileAnalysisService(data_sources, ai_client=FailingAiClient())


def _profile(
    country_code: str,
    product_category: str,
    keyword: str | None,
    hs_code: str | None,
) -> MarketProfileAnalysisResponse:
    return MarketProfileAnalysisResponse(
        country_code=country_code,
        country_name=country_code,
        product_category=product_category,
        keyword=keyword,
        hs_code=hs_code,
        market_size_score=80,
        consumption_power_score=82,
        internet_score=90,
        trade_score=70,
        logistics_score=75,
        competition_level="high",
        suitable_products=[
            SuitableProductItem(
                product_key="P001",
                product_name_cn="sample",
                product_name_en="Sample Product",
                category="Home Textile",
                hs_code="6302",
                fit_score=81,
                reason="Sample reason",
                evidence=["sample evidence"],
            )
        ],
        summary="Sample summary",
        fallback_used=True,
        ai_fallback_used=True,
        sources=[
            AnalysisSource(
                provider="csv_seed",
                source_label="CSV fallback: market_profiles.csv",
                source_type="csv_fallback",
                fallback_used=True,
            )
        ],
        evidence={"trade_value": str(Decimal("1000"))},
    )


def _sort_score(item: MarketProfileAnalysisResponse) -> float:
    return (
        item.market_size_score * 0.25
        + item.consumption_power_score * 0.20
        + item.internet_score * 0.15
        + item.trade_score * 0.25
        + item.logistics_score * 0.15
    )
