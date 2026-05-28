from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.api.data_sources import get_data_source_service
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import ApiCallLog, DataSourceCache
from app.schemas import (
    DataSourceCompetitorItem,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendItem,
    DataSourceContentTrendResponse,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
)

_ = _models


def test_data_source_post_routes_map_requests_to_service(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    service = StubDataSourceService()
    app.dependency_overrides[get_data_source_service] = lambda: service

    competitors = client.post(
        "/api/data-sources/search-competitors",
        json={"keyword": "boho blanket", "country": "US", "limit": 5},
    )
    trends = client.post(
        "/api/data-sources/search-trends",
        json={"query": "home decor", "country": "GB", "limit": 8},
    )
    profile = client.post("/api/data-sources/market-profile", json={"country_code": "US"})
    trade = client.post(
        "/api/data-sources/trade-data",
        json={"product_category": "cotton bedding", "hs_code": "630221", "country": "US"},
    )

    assert competitors.status_code == 200
    assert trends.status_code == 200
    assert profile.status_code == 200
    assert trade.status_code == 200
    assert competitors.json()["items"][0]["platform"] == "Etsy"
    assert trends.json()["items"][0]["platform"] == "YouTube"
    assert profile.json()["country_code"] == "US"
    assert trade.json()["hs_code"] == "630221"
    assert service.calls == [
        ("search_competitors", "boho blanket", "US", 5),
        ("get_content_trends", "home decor", "GB", 8),
        ("get_market_profile", "US"),
        ("get_trade_data", "cotton bedding", "630221", "US"),
    ]


def test_cache_status_summarizes_fresh_and_expired_entries(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        db.add(
            DataSourceCache(
                provider="youtube",
                endpoint="search_video_trends",
                query="home decor|limit:10",
                country="US",
                response_payload={"provider": "youtube", "keyword": "home decor", "country": "US", "items": []},
                fallback_used=False,
                source="api",
                fetched_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.add(
            DataSourceCache(
                provider="youtube",
                endpoint="search_video_trends",
                query="boho bedroom|limit:10",
                country="US",
                response_payload={"provider": "youtube", "keyword": "boho bedroom", "country": "US", "items": []},
                fallback_used=True,
                source="csv_fallback",
                fetched_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            )
        )
        db.commit()

    response = client.get("/api/data-sources/cache-status")

    assert response.status_code == 200
    payload = response.json()
    item = payload["items"][0]
    assert item["provider"] == "youtube"
    assert item["endpoint"] == "search_video_trends"
    assert item["fresh_count"] == 1
    assert item["expired_count"] == 1


def test_logs_endpoint_filters_and_orders_without_secret_values(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    first_called_at = datetime(2026, 5, 28, 9, 0, tzinfo=timezone.utc)
    second_called_at = datetime(2026, 5, 28, 9, 5, tzinfo=timezone.utc)
    with session_factory() as db:
        db.add(
            ApiCallLog(
                provider="youtube",
                endpoint="search_video_trends",
                query='{"keyword":"home decor","country":"US"}',
                status="success",
                response_time_ms=12,
                fallback_used=False,
                error_message=None,
                called_at=first_called_at,
            )
        )
        db.add(
            ApiCallLog(
                provider="etsy",
                endpoint="search_competitors",
                query='{"keyword":"boho blanket","country":"US"}',
                status="fallback",
                response_time_ms=4,
                fallback_used=True,
                error_message="Provider failed or unavailable; CSV fallback used.",
                called_at=second_called_at,
            )
        )
        db.commit()

    response = client.get("/api/data-sources/logs?provider=etsy&status=fallback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["provider"] == "etsy"
    assert payload["items"][0]["status"] == "fallback"
    serialized = response.text.casefold()
    assert "fake-key" not in serialized
    assert "authorization" not in serialized
    assert "x-api-key" not in serialized
    assert "subscription-key" not in serialized


def test_data_source_routes_return_422_for_invalid_service_input(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    service = InvalidInputService()
    app.dependency_overrides[get_data_source_service] = lambda: service

    response = client.post("/api/data-sources/market-profile", json={"country_code": "US"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_DATA_SOURCE_INPUT"


class StubDataSourceService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def search_competitors(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 20,
    ) -> DataSourceCompetitorSearchResponse:
        self.calls.append(("search_competitors", keyword, country, limit))
        return DataSourceCompetitorSearchResponse(
            keyword=keyword,
            country=country or "US",
            items=[
                DataSourceCompetitorItem(
                    platform="Etsy",
                    country=country or "US",
                    keyword=keyword,
                    title="Boho listing",
                    price=Decimal("42.00"),
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
        self.calls.append(("get_content_trends", keyword, country, limit))
        return DataSourceContentTrendResponse(
            keyword=keyword,
            country=country,
            items=[
                DataSourceContentTrendItem(
                    platform="YouTube",
                    country=country,
                    keyword=keyword,
                    title="Home decor video",
                    url="https://sample.example/video",
                    source_type="api",
                )
            ],
            fallback_used=False,
            sources=["YouTube"],
        )

    async def get_market_profile(self, country_code: str) -> WorldBankCountryResponse:
        self.calls.append(("get_market_profile", country_code))
        return WorldBankCountryResponse(
            country_code=country_code,
            indicators=[
                WorldBankIndicatorItem(
                    indicator_code="SP.POP.TOTL",
                    indicator_name="Population, total",
                    year=2024,
                    value=1000,
                    source="api",
                )
            ],
            fallback_used=False,
        )

    async def get_trade_data(
        self,
        product_category: str,
        hs_code: str | None = None,
        country: str | None = None,
    ) -> UnComtradeTradeFlowResponse:
        self.calls.append(("get_trade_data", product_category, hs_code, country))
        return UnComtradeTradeFlowResponse(
            hs_code=hs_code or "6302",
            reporter="CHN",
            partner="USA",
            flow="export",
            records=[
                UnComtradeTradeRecord(
                    year=2024,
                    trade_value_usd=Decimal("1000"),
                    quantity=Decimal("10"),
                    source="api",
                )
            ],
            fallback_used=False,
            auth_mode="no_key",
        )


class InvalidInputService(StubDataSourceService):
    async def get_market_profile(self, country_code: str) -> WorldBankCountryResponse:
        raise ValueError("invalid country")


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
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
