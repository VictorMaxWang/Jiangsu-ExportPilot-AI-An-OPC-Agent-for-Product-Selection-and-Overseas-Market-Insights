from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.core.admin_auth import require_admin_auth
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import ApiCallLog, CompetitorItem, DataSourceCache, YoutubeSearchCache

_ = _models


def test_provider_cache_clear_deletes_only_matching_data_source_cache(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        db.add_all(
            [
                _cache_row("youtube", "search_video_trends", "home decor", "US", now),
                _cache_row("youtube", "search_video_trends", "boho bedroom", "US", now),
                _cache_row("etsy", "search_competitors", "home decor", "US", now),
                ApiCallLog(
                    provider="youtube",
                    endpoint="search_video_trends",
                    query='{"keyword":"home decor"}',
                    status="success",
                    response_time_ms=1,
                    fallback_used=False,
                    called_at=now,
                ),
                CompetitorItem(
                    platform="Etsy",
                    country="US",
                    keyword="home decor",
                    title="sample",
                    price=Decimal("10.00"),
                    source_type="api",
                ),
            ]
        )
        db.commit()

    response = client.post("/api/admin/cache/clear/youtube")

    assert response.status_code == 200
    assert response.json()["cache_table"] == "data_source_caches"
    assert response.json()["provider"] == "youtube"
    assert response.json()["cleared_count"] == 2
    assert "fake-key" not in response.text
    assert "authorization" not in response.text.casefold()
    assert "x-api-key" not in response.text.casefold()
    assert "subscription-key" not in response.text.casefold()
    with session_factory() as db:
        cache_providers = set(db.scalars(select(DataSourceCache.provider)))
        log_count = db.scalar(select(func.count()).select_from(ApiCallLog))
        competitor_count = db.scalar(select(func.count()).select_from(CompetitorItem))
    assert cache_providers == {"etsy"}
    assert log_count == 1
    assert competitor_count == 1


def test_cache_clear_without_provider_deletes_all_data_source_cache(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        db.add_all(
            [
                _cache_row("youtube", "search_video_trends", "home decor", "US", now),
                _cache_row("etsy", "search_competitors", "home decor", "US", now),
                YoutubeSearchCache(
                    keyword="home decor",
                    country="US",
                    source="api",
                    items=[],
                    fetched_at=now,
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        db.commit()

    response = client.post("/api/admin/cache/clear")

    assert response.status_code == 200
    assert response.json()["cache_table"] == "data_source_caches"
    assert response.json()["provider"] is None
    assert response.json()["cleared_count"] == 2
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DataSourceCache)) == 0
        assert db.scalar(select(func.count()).select_from(YoutubeSearchCache)) == 1


def test_cache_clear_unknown_provider_is_idempotent(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    response = client.post("/api/admin/cache/clear/missing")

    assert response.status_code == 200
    assert response.json()["cleared_count"] == 0


def test_cache_clear_database_error_is_sanitized() -> None:
    def override_get_db() -> Generator[FailingCacheSession, None, None]:
        yield FailingCacheSession()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_auth] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/api/admin/cache/clear/youtube")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_admin_auth, None)

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "DATA_SOURCE_CACHE_CLEAR_FAILED"
    serialized = response.text.casefold()
    assert "fake-key" not in serialized
    assert "authorization" not in serialized
    assert "x-api-key" not in serialized
    assert "subscription-key" not in serialized


def _cache_row(provider: str, endpoint: str, query: str, country: str, now: datetime) -> DataSourceCache:
    return DataSourceCache(
        provider=provider,
        endpoint=endpoint,
        query=query,
        country=country,
        response_payload={"provider": provider, "items": []},
        fallback_used=False,
        source="api",
        fetched_at=now,
        expires_at=now + timedelta(hours=1),
    )


class FailingCacheSession:
    def scalar(self, _statement: object) -> int:
        raise SQLAlchemyError("authorization fake-key x-api-key")

    def rollback(self) -> None:
        pass


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
    app.dependency_overrides[require_admin_auth] = lambda: None
    with TestClient(app) as test_client:
        yield test_client, testing_session_local
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_admin_auth, None)
    Base.metadata.drop_all(bind=engine)
