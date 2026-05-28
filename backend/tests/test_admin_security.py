from __future__ import annotations

import base64
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app, create_app
from app.models import DataSourceCache, YoutubeSearchCache
from app.schemas import WorldBankCountryResponse
from app.services.provider_status import ProviderStatusService, get_provider_status_service


ADMIN_PASSWORD = "admin-test-password"
SENTINEL_SECRET = "provider-test-secret"


def test_local_default_allows_admin_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 200
    get_settings.cache_clear()


def test_explicit_disabled_allows_admin_status_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 200
    get_settings.cache_clear()


def test_production_admin_requires_password_without_leaking_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "ADMIN_AUTH_REQUIRED"
    _assert_no_admin_secret(response.text)
    get_settings.cache_clear()


def test_enabled_admin_without_configured_password_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status", headers={"X-Admin-Password": ADMIN_PASSWORD})

    assert response.status_code == 401
    _assert_no_admin_secret(response.text)
    get_settings.cache_clear()


def test_admin_accepts_header_and_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_admin_auth(monkeypatch)
    basic_credentials = base64.b64encode(f"admin:{ADMIN_PASSWORD}".encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        header_response = client.get("/api/admin/providers/status", headers={"X-Admin-Password": ADMIN_PASSWORD})
        basic_response = client.get(
            "/api/admin/providers/status",
            headers={"Authorization": f"Basic {basic_credentials}"},
        )
        wrong_response = client.get("/api/admin/providers/status", headers={"X-Admin-Password": "wrong-password"})

    assert header_response.status_code == 200
    assert basic_response.status_code == 200
    assert wrong_response.status_code == 401
    _assert_no_admin_secret(wrong_response.text)
    get_settings.cache_clear()


def test_provider_test_response_does_not_leak_secret_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_admin_auth(monkeypatch)
    service = ProviderStatusService(settings=get_settings(), worldbank_provider=SecretFailingWorldBankProvider())
    app.dependency_overrides[get_provider_status_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/admin/providers/test/worldbank",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
            )
    finally:
        app.dependency_overrides.pop(get_provider_status_service, None)
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert SENTINEL_SECRET not in response.text
    assert "Authorization" not in response.text
    assert "Bearer" not in response.text


def test_admin_cache_clear_is_protected_and_clears_cache(
    monkeypatch: pytest.MonkeyPatch,
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _enable_admin_auth(monkeypatch)
    client, session_factory = client_with_session
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        db.add(
            DataSourceCache(
                provider="youtube",
                endpoint="search_video_trends",
                query="home decor",
                country="US",
                response_payload={"items": []},
                fallback_used=False,
                source="api",
                fetched_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.add(
            YoutubeSearchCache(
                keyword="home decor",
                country="US",
                source="api",
                items=[],
                fetched_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

    blocked = client.post("/api/admin/cache/clear")
    cleared = client.post("/api/admin/cache/clear", headers={"X-Admin-Password": ADMIN_PASSWORD})

    assert blocked.status_code == 401
    assert cleared.status_code == 200
    assert cleared.json()["cache_table"] == "data_source_caches"
    assert cleared.json()["cleared_count"] == 1
    with session_factory() as db:
        assert db.scalar(select(DataSourceCache)) is None
        assert db.scalar(select(YoutubeSearchCache)) is not None
    get_settings.cache_clear()


def test_production_cors_filters_wildcard_and_allows_configured_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("PUBLIC_SITE_ORIGIN", "https://export.example.com")
    monkeypatch.setenv("ALLOWED_ADMIN_ORIGINS", "https://opc.ankangyu.cn")
    get_settings.cache_clear()

    test_app = create_app()
    with TestClient(test_app) as client:
        allowed = client.options(
            "/health",
            headers={
                "Origin": "https://export.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        admin_allowed = client.options(
            "/health",
            headers={
                "Origin": "https://opc.ankangyu.cn",
                "Access-Control-Request-Method": "GET",
            },
        )
        blocked = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.headers["access-control-allow-origin"] == "https://export.example.com"
    assert admin_allowed.headers["access-control-allow-origin"] == "https://opc.ankangyu.cn"
    assert blocked.headers.get("access-control-allow-origin") != "*"
    assert blocked.headers.get("access-control-allow-origin") is None
    get_settings.cache_clear()


class SecretFailingWorldBankProvider:
    async def fetch_country(self, _country_code: str) -> WorldBankCountryResponse:
        raise RuntimeError(f"Authorization: Bearer {SENTINEL_SECRET}")


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
    Base.metadata.drop_all(bind=engine)


def _enable_admin_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_admin_env(monkeypatch)
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "true")
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    get_settings.cache_clear()


def _clear_admin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "APP_ENV",
        "ADMIN_AUTH_ENABLED",
        "ADMIN_PASSWORD",
        "SUPIN_APP_ENV",
        "SUPIN_ADMIN_AUTH_ENABLED",
        "SUPIN_ADMIN_PASSWORD",
        "PUBLIC_SITE_ORIGIN",
        "ALLOWED_ADMIN_ORIGINS",
        "CORS_ORIGINS",
    ):
        monkeypatch.delenv(name, raising=False)


def _assert_no_admin_secret(text: str) -> None:
    assert ADMIN_PASSWORD not in text
    assert "wrong-password" not in text
    assert "Authorization" not in text
    assert "Bearer" not in text
