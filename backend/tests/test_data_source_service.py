import asyncio
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import Base
from app.models import ApiCallLog, DataSourceCache
from app.schemas import (
    GdeltSearchResponse,
    WorldBankCountryResponse,
    YoutubeSearchResponse,
)
from app.services.data_sources import DataSourceService


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


def test_worldbank_fallback_uses_market_profiles_csv(db_session: Session) -> None:
    service = DataSourceService(db_session, worldbank_provider=FailingWorldBankProvider())

    result = asyncio.run(service.get_market_profile("US"))

    assert isinstance(result, WorldBankCountryResponse)
    assert result.country_code == "US"
    assert result.fallback_used is True
    assert {item.indicator_code for item in result.indicators} >= {
        "NY.GDP.MKTP.CD",
        "NY.GDP.PCAP.CD",
        "SP.POP.TOTL",
        "IT.NET.USER.ZS",
    }
    assert _latest_log(db_session).provider == "worldbank"
    assert _latest_log(db_session).status == "fallback"


def test_gdelt_unsupported_query_falls_back_to_gdelt_sample_rows(db_session: Session) -> None:
    service = DataSourceService(db_session, gdelt_provider=FailingGdeltProvider())

    result = asyncio.run(service.search_news_trends("unknown trend", country="US"))

    assert isinstance(result, GdeltSearchResponse)
    assert result.fallback_used is True
    assert result.items
    assert all(item.source == "csv_fallback" for item in result.items)
    assert all(item.domain == "sample.example" for item in result.items)


def test_youtube_fallback_is_cached_and_logs_cache_hit(db_session: Session) -> None:
    provider = FailingYoutubeProvider()
    service = DataSourceService(db_session, youtube_provider=provider)

    first = asyncio.run(service.search_video_trends("home decor", country="US"))
    second = asyncio.run(service.search_video_trends(" home   decor ", country="us"))

    assert isinstance(first, YoutubeSearchResponse)
    assert first.fallback_used is True
    assert second.items[0].video_url == first.items[0].video_url
    assert provider.calls == 1
    assert _cache_providers(db_session) == {"youtube"}
    assert _log_statuses(db_session) == ["fallback", "cache_hit"]


def test_etsy_fallback_uses_full_competitor_samples_and_is_cached(db_session: Session) -> None:
    provider = FailingEtsyProvider()
    service = DataSourceService(db_session, etsy_provider=provider)

    first = asyncio.run(service.search_competitors("boho blanket", country="US", limit=12))
    second = asyncio.run(service.search_competitors("boho blanket", country="US", limit=12))

    assert first.fallback_used is True
    assert first.items
    assert "Etsy Sample" in first.sources
    assert len(first.sources) > 1
    assert second.items[0].product_url == first.items[0].product_url
    assert provider.calls == 1
    assert _log_statuses(db_session) == ["fallback", "cache_hit"]


def test_un_comtrade_fallback_is_cached(db_session: Session) -> None:
    provider = FailingUnComtradeProvider()
    service = DataSourceService(db_session, un_comtrade_provider=provider)

    first = asyncio.run(service.get_trade_data("cotton bedding", country="US"))
    second = asyncio.run(service.get_trade_data(" cotton   bedding ", country="us"))

    assert first.fallback_used is True
    assert first.auth_mode == "fallback"
    assert first.hs_code == "630221"
    assert {record.year for record in first.records} == {2020, 2021, 2022, 2023, 2024}
    assert second.records[0].trade_value_usd == first.records[0].trade_value_usd
    assert provider.calls == 1
    assert _cache_providers(db_session) == {"un_comtrade"}


def test_content_trends_survives_provider_failures(db_session: Session) -> None:
    service = DataSourceService(
        db_session,
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
    )

    result = asyncio.run(service.get_content_trends("home decor", country="US", limit=15))

    assert result.items
    assert result.fallback_used is True
    assert {"GDELT Sample", "YouTube", "TikTok Sample", "Pinterest Sample"} & set(result.sources)


def test_optional_providers_are_not_called_or_logged(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EBAY_CLIENT_ID", "fake-ebay-key")
    monkeypatch.setenv("RAKUTEN_APP_ID", "fake-rakuten-key")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "fake-reddit-key")
    get_settings.cache_clear()

    service = DataSourceService(
        db_session,
        etsy_provider=FailingEtsyProvider(),
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
    )

    asyncio.run(service.search_competitors("home decor", country="US"))
    asyncio.run(service.get_content_trends("home decor", country="US"))

    providers = _cache_providers(db_session) | set(db_session.scalars(select(ApiCallLog.provider)))
    assert "ebay" not in providers
    assert "rakuten" not in providers
    assert "reddit" not in providers
    get_settings.cache_clear()


def test_log_error_messages_are_sanitized(db_session: Session) -> None:
    service = DataSourceService(db_session, etsy_provider=SecretFailingEtsyProvider())

    asyncio.run(service.search_competitors("home decor", country="US"))

    log = _latest_log(db_session)
    assert log.error_message == "Provider failed or unavailable; CSV fallback used."
    serialized = log.error_message or ""
    assert "fake-key" not in serialized
    assert "authorization" not in serialized.casefold()
    assert "x-api-key" not in serialized.casefold()
    assert "subscription-key" not in serialized.casefold()


class FailingWorldBankProvider:
    async def fetch_country(self, _country_code: str) -> WorldBankCountryResponse:
        raise RuntimeError("https://example.invalid?key=fake-key")


class FailingGdeltProvider:
    async def search(
        self,
        _query: str,
        *,
        country: str | None = None,
        max_records: int = 10,
    ) -> GdeltSearchResponse:
        raise RuntimeError("GDELT unavailable")


class FailingYoutubeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search_videos(
        self,
        _keyword: str,
        country: str = "US",
        max_results: int = 10,
    ) -> YoutubeSearchResponse:
        self.calls += 1
        raise RuntimeError("youtube x-api-key fake-key unavailable")


class FailingEtsyProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search_listings(self, _keyword: str, country: str = "US", limit: int = 20) -> object:
        self.calls += 1
        raise RuntimeError("etsy unavailable")


class SecretFailingEtsyProvider(FailingEtsyProvider):
    async def search_listings(self, _keyword: str, country: str = "US", limit: int = 20) -> object:
        self.calls += 1
        raise RuntimeError("authorization x-api-key subscription-key fake-key")


class FailingUnComtradeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def get_trade_flow(
        self,
        reporter: str = "CHN",
        partner: str = "USA",
        hs_code: str = "6302",
        flow: str = "export",
        start_year: int = 2020,
        end_year: int = 2024,
    ) -> object:
        self.calls += 1
        raise RuntimeError("subscription-key fake-key unavailable")


def _latest_log(db: Session) -> ApiCallLog:
    log = db.scalar(select(ApiCallLog).order_by(ApiCallLog.id.desc()).limit(1))
    assert log is not None
    return log


def _log_statuses(db: Session) -> list[str]:
    return list(db.scalars(select(ApiCallLog.status).order_by(ApiCallLog.id)))


def _cache_providers(db: Session) -> set[str]:
    return set(db.scalars(select(DataSourceCache.provider)))
