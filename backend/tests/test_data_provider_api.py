from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.api.data import (
    get_etsy_provider,
    get_gdelt_provider,
    get_un_comtrade_provider,
    get_worldbank_provider,
    get_youtube_provider,
)
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import CompetitorItem, ContentTrend, MarketIndicator, NewsItem, TradeStat, YoutubeSearchCache
from app.schemas import (
    EtsyListingItem,
    EtsySearchResponse,
    GdeltArticleItem,
    GdeltSearchResponse,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
    YoutubeSearchResponse,
    YoutubeVideoItem,
)

_ = _models


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


def test_worldbank_country_route_returns_provider_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    provider = StubWorldBankProvider()
    app.dependency_overrides[get_worldbank_provider] = lambda: provider

    response = client.get("/api/data/worldbank/country/us")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "worldbank"
    assert payload["country_code"] == "US"
    assert payload["fallback_used"] is False
    assert payload["indicators"][0]["source"] == "api"
    assert provider.calls == ["us"]


def test_worldbank_sync_endpoint_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_worldbank_provider] = lambda: StubWorldBankProvider()

    first_response = client.post("/api/data/worldbank/sync")
    second_response = client.post("/api/data/worldbank/sync")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["requested"] == 20
    assert first_response.json()["inserted"] == 20
    assert first_response.json()["updated"] == 0
    assert second_response.json()["inserted"] == 0
    assert second_response.json()["updated"] == 20
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(MarketIndicator))
        sources = set(db.scalars(select(MarketIndicator.source)))
    assert count == 20
    assert sources == {"worldbank_api"}


def test_worldbank_sync_endpoint_accepts_fallback_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_worldbank_provider] = lambda: StubWorldBankProvider(fallback=True)

    response = client.post("/api/data/worldbank/sync")

    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    with session_factory() as db:
        sources = set(db.scalars(select(MarketIndicator.source)))
    assert sources == {"worldbank_csv_fallback"}


def test_gdelt_search_route_returns_provider_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    provider = StubGdeltProvider()
    app.dependency_overrides[get_gdelt_provider] = lambda: provider

    response = client.get("/api/data/gdelt/search?query=home%20decor&country=GB")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gdelt"
    assert payload["query"] == "home decor"
    assert payload["items"][0]["source"] == "api"
    assert provider.calls == [("home decor", "GB")]


def test_gdelt_sync_endpoint_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_gdelt_provider] = lambda: StubGdeltProvider()

    first_response = client.post("/api/data/gdelt/sync")
    second_response = client.post("/api/data/gdelt/sync")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["inserted"] == 7
    assert first_response.json()["updated"] == 0
    assert second_response.json()["inserted"] == 0
    assert second_response.json()["updated"] == 7
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(NewsItem))
        sources = set(db.scalars(select(NewsItem.source)))
    assert count == 7
    assert sources == {"gdelt_api"}


def test_gdelt_sync_endpoint_accepts_fallback_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_gdelt_provider] = lambda: StubGdeltProvider(fallback=True)

    response = client.post("/api/data/gdelt/sync")

    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    with session_factory() as db:
        sources = set(db.scalars(select(NewsItem.source)))
    assert sources == {"gdelt_csv_fallback"}


def test_youtube_search_route_returns_provider_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    provider = StubYoutubeProvider()
    app.dependency_overrides[get_youtube_provider] = lambda: provider

    response = client.get("/api/data/youtube/search?keyword=home%20decor&country=GB&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "youtube"
    assert payload["keyword"] == "home decor"
    assert payload["country"] == "GB"
    assert payload["fallback_used"] is False
    assert payload["items"][0]["source_type"] == "api"
    assert "fake-key" not in response.text
    assert provider.calls == [("home decor", "GB", 10)]


def test_youtube_search_endpoint_uses_24_hour_cache(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "cache-fake-key")
    get_settings.cache_clear()
    client, session_factory = client_with_session
    provider = StubYoutubeProvider()
    app.dependency_overrides[get_youtube_provider] = lambda: provider

    first_response = client.get("/api/data/youtube/search?keyword=%20Boho%20%20Bedroom%20&country=us&limit=3")
    second_response = client.get("/api/data/youtube/search?keyword=boho%20bedroom&country=US&limit=3")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert provider.calls == [("boho bedroom", "US", 10)]
    assert second_response.json()["items"][0]["video_url"] == first_response.json()["items"][0]["video_url"]
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(YoutubeSearchCache))
    assert count == 1
    get_settings.cache_clear()


def test_youtube_search_endpoint_refreshes_expired_cache(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "expired-cache-fake-key")
    get_settings.cache_clear()
    client, session_factory = client_with_session
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with session_factory() as db:
        db.add(
            YoutubeSearchCache(
                keyword="home decor",
                country="US",
                source="api",
                items=[],
                fetched_at=expired_at - timedelta(hours=24),
                expires_at=expired_at,
            )
        )
        db.commit()

    provider = StubYoutubeProvider()
    app.dependency_overrides[get_youtube_provider] = lambda: provider

    response = client.get("/api/data/youtube/search?keyword=home%20decor&country=US")

    assert response.status_code == 200
    assert provider.calls == [("home decor", "US", 10)]
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(YoutubeSearchCache))
        cache = db.scalar(select(YoutubeSearchCache).where(YoutubeSearchCache.keyword == "home decor"))
    assert count == 1
    assert cache is not None
    assert cache.items[0]["title"] == "home decor video"
    get_settings.cache_clear()


def test_youtube_sync_endpoint_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_youtube_provider] = lambda: StubYoutubeProvider()

    first_response = client.post("/api/data/youtube/sync")
    second_response = client.post("/api/data/youtube/sync")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["provider"] == "youtube"
    assert first_response.json()["requested"] == 50
    assert first_response.json()["inserted"] == 50
    assert first_response.json()["updated"] == 0
    assert second_response.json()["inserted"] == 0
    assert second_response.json()["updated"] == 50
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(ContentTrend))
        platforms = set(db.scalars(select(ContentTrend.platform)))
        styles = set(db.scalars(select(ContentTrend.content_style)))
    assert count == 50
    assert platforms == {"YouTube"}
    assert styles == {"api"}


def test_etsy_search_route_returns_provider_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    provider = StubEtsyProvider()
    app.dependency_overrides[get_etsy_provider] = lambda: provider

    response = client.get("/api/data/etsy/search?keyword=boho%20bedroom&country=US&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "etsy"
    assert payload["keyword"] == "boho bedroom"
    assert payload["country"] == "US"
    assert payload["fallback_used"] is False
    assert payload["items"][0]["platform"] == "Etsy"
    assert payload["items"][0]["source_type"] == "api"
    assert "fake-key" not in response.text
    assert "fake-secret" not in response.text
    assert provider.calls == [("boho bedroom", "US", 5)]


def test_etsy_sync_endpoint_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_etsy_provider] = lambda: StubEtsyProvider()

    first_response = client.post("/api/data/etsy/sync")
    second_response = client.post("/api/data/etsy/sync")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["provider"] == "etsy"
    assert first_response.json()["requested"] == 50
    assert first_response.json()["inserted"] == 50
    assert first_response.json()["updated"] == 0
    assert second_response.json()["inserted"] == 0
    assert second_response.json()["updated"] == 50
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(CompetitorItem))
        platforms = set(db.scalars(select(CompetitorItem.platform)))
        source_types = set(db.scalars(select(CompetitorItem.source_type)))
    assert count == 50
    assert platforms == {"Etsy"}
    assert source_types == {"api"}


def test_etsy_sync_endpoint_accepts_fallback_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_etsy_provider] = lambda: StubEtsyProvider(fallback=True)

    response = client.post("/api/data/etsy/sync")

    assert response.status_code == 200
    assert response.json()["provider"] == "etsy"
    assert response.json()["fallback_used"] is True
    with session_factory() as db:
        source_types = set(db.scalars(select(CompetitorItem.source_type)))
    assert source_types == {"csv_fallback"}


def test_un_comtrade_trade_flow_route_returns_provider_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    provider = StubUnComtradeProvider()
    app.dependency_overrides[get_un_comtrade_provider] = lambda: provider

    response = client.get(
        "/api/data/comtrade/trade-flow"
        "?reporter=CHN&partner=USA&hs_code=6302&flow=export&start_year=2023&end_year=2024"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "un_comtrade"
    assert payload["hs_code"] == "6302"
    assert payload["reporter"] == "CHN"
    assert payload["partner"] == "USA"
    assert payload["flow"] == "export"
    assert payload["fallback_used"] is False
    assert payload["auth_mode"] == "no_key"
    assert payload["records"][0]["source"] == "api"
    assert "fake-key" not in response.text
    assert provider.calls == [("CHN", "USA", "6302", "export", 2023, 2024)]


def test_un_comtrade_sync_endpoint_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_un_comtrade_provider] = lambda: StubUnComtradeProvider()

    first_response = client.post("/api/data/comtrade/sync")
    second_response = client.post("/api/data/comtrade/sync")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["provider"] == "un_comtrade"
    assert first_response.json()["requested"] == 20
    assert first_response.json()["inserted"] == 40
    assert first_response.json()["updated"] == 0
    assert second_response.json()["inserted"] == 0
    assert second_response.json()["updated"] == 40
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(TradeStat))
        sources = set(db.scalars(select(TradeStat.source)))
        reporters = set(db.scalars(select(TradeStat.reporter)))
    assert count == 40
    assert sources == {"un_comtrade_api_no_key"}
    assert reporters == {"CHN"}


def test_un_comtrade_sync_endpoint_accepts_fallback_payload(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    app.dependency_overrides[get_un_comtrade_provider] = lambda: StubUnComtradeProvider(fallback=True)

    response = client.post("/api/data/comtrade/sync")

    assert response.status_code == 200
    assert response.json()["provider"] == "un_comtrade"
    assert response.json()["fallback_used"] is True
    assert "fake-key" not in response.text
    with session_factory() as db:
        sources = set(db.scalars(select(TradeStat.source)))
    assert sources == {"un_comtrade_csv_fallback"}


def test_data_provider_routes_return_422_for_unsupported_inputs(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    worldbank_response = client.get("/api/data/worldbank/country/ZZ")
    gdelt_response = client.get("/api/data/gdelt/search?query=unsupported")
    youtube_response = client.get("/api/data/youtube/search?keyword=home%20decor&country=USA")
    etsy_response = client.get("/api/data/etsy/search?keyword=home%20decor&country=USA")
    comtrade_response = client.get("/api/data/comtrade/trade-flow?reporter=ZZZ")

    assert worldbank_response.status_code == 422
    assert gdelt_response.status_code == 422
    assert youtube_response.status_code == 422
    assert etsy_response.status_code == 422
    assert comtrade_response.status_code == 422
    assert worldbank_response.json()["detail"]["provider"] == "worldbank"
    assert gdelt_response.json()["detail"]["provider"] == "gdelt"
    assert etsy_response.json()["detail"]["provider"] == "etsy"
    assert comtrade_response.json()["detail"]["provider"] == "un_comtrade"


class StubWorldBankProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[str] = []

    async def fetch_country(self, country_code: str) -> WorldBankCountryResponse:
        self.calls.append(country_code)
        normalized = country_code.upper()
        return WorldBankCountryResponse(
            country_code=normalized,
            indicators=[
                WorldBankIndicatorItem(
                    indicator_code="SP.POP.TOTL",
                    indicator_name="Population, total",
                    year=2024,
                    value=1000.0,
                    source="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubGdeltProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[tuple[str, str | None]] = []

    async def search(
        self,
        query: str,
        *,
        country: str | None = None,
        max_records: int = 10,
    ) -> GdeltSearchResponse:
        self.calls.append((query, country))
        slug = query.lower().replace(" ", "-")
        return GdeltSearchResponse(
            query=query,
            items=[
                GdeltArticleItem(
                    title=f"{query} trend",
                    url=f"https://news.example/{slug}",
                    domain="news.example",
                    published_at="2026-05-27T12:00:00+00:00",
                    language="English",
                    source="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubYoutubeProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[tuple[str, str, int]] = []

    async def search_videos(
        self,
        keyword: str,
        country: str = "US",
        max_results: int = 10,
    ) -> YoutubeSearchResponse:
        self.calls.append((keyword, country, max_results))
        slug = keyword.lower().replace(" ", "-")
        return YoutubeSearchResponse(
            keyword=keyword,
            country=country,
            items=[
                YoutubeVideoItem(
                    country=country,
                    keyword=keyword,
                    title=f"{keyword} video",
                    channel_title="Sample Channel",
                    published_at="2026-05-27T12:00:00+00:00",
                    thumbnail_url="https://img.example/youtube.jpg",
                    video_url=f"https://www.youtube.com/watch?v={country.lower()}-{slug}",
                    description="Sample YouTube trend.",
                    source_type="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubEtsyProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[tuple[str, str, int]] = []

    async def search_listings(
        self,
        keyword: str,
        country: str = "US",
        limit: int = 20,
    ) -> EtsySearchResponse:
        self.calls.append((keyword, country, limit))
        slug = keyword.lower().replace(" ", "-")
        return EtsySearchResponse(
            keyword=keyword,
            country=country,
            items=[
                EtsyListingItem(
                    country=country,
                    keyword=keyword,
                    title=f"{keyword} listing",
                    price=Decimal("46.00"),
                    currency="USD",
                    image_url="https://img.example/etsy.jpg",
                    product_url=f"https://www.etsy.com/listing/{country.lower()}-{slug}",
                    category="Home & Living",
                    rating=Decimal("4.80"),
                    review_count=312,
                    source_type="csv_fallback" if self.fallback else "api",
                    collected_at=datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc),
                )
            ],
            fallback_used=self.fallback,
        )


class StubUnComtradeProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[tuple[str, str, str, str, int, int]] = []

    async def get_trade_flow(
        self,
        reporter: str = "CHN",
        partner: str = "USA",
        hs_code: str = "6302",
        flow: str = "export",
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> UnComtradeTradeFlowResponse:
        self.calls.append((reporter, partner, hs_code, flow, start_year, end_year))
        source = "csv_fallback" if self.fallback else "api"
        auth_mode = "fallback" if self.fallback else "no_key"
        return UnComtradeTradeFlowResponse(
            hs_code=hs_code,
            reporter=reporter,
            partner=partner,
            flow="import" if flow.lower().startswith("import") else "export",
            records=[
                UnComtradeTradeRecord(
                    year=start_year,
                    trade_value_usd=Decimal("1000"),
                    quantity=Decimal("10"),
                    source=source,
                ),
                UnComtradeTradeRecord(
                    year=end_year,
                    trade_value_usd=Decimal("1200"),
                    quantity=Decimal("12"),
                    source=source,
                ),
            ],
            fallback_used=self.fallback,
            auth_mode=auth_mode,
        )
