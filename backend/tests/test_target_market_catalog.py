from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.core.countries import TARGET_COUNTRY_CODES
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AnalysisCountryPreset, TargetCountry
from app.services.target_market_catalog import TargetMarketCatalogError, TargetMarketCatalogService

_ = _models

COUNTRY_PRESETS = {
    "FIVE_CONTINENT_REPS": ["JP", "DE", "US", "AU", "ZA"],
    "MATURE_WESTERN_MARKETS": ["US", "CA", "GB", "DE", "FR", "NL", "IT"],
    "EAST_AND_SEA": ["JP", "KR", "SG", "MY"],
    "BELT_ROAD_POTENTIAL": ["MY", "AE", "EG", "ZA"],
}


def test_market_catalog_api_returns_csv_fallback_when_db_empty(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    countries = client.get("/api/markets/countries")
    presets = client.get("/api/markets/presets")

    assert countries.status_code == 200
    country_payload = countries.json()
    assert country_payload["source"] == "csv_fallback"
    assert country_payload["total"] == 19
    assert [item["country_code"] for item in country_payload["items"]] == list(TARGET_COUNTRY_CODES)
    assert all(item["source"] == "csv_fallback" for item in country_payload["items"])

    assert presets.status_code == 200
    preset_payload = presets.json()
    assert preset_payload["source"] == "csv_fallback"
    assert preset_payload["total"] == 4
    assert {
        item["preset_code"]: item["country_codes"]
        for item in preset_payload["items"]
    } == COUNTRY_PRESETS


def test_market_catalog_api_uses_database_when_rows_exist_and_filters(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    with session_factory() as db:
        db.add_all(
            [
                TargetCountry(
                    country_code="US",
                    name_cn="美国",
                    name_en="United States",
                    region_code="NORTH_AMERICA",
                    continent="North America",
                    default_sort_order=2,
                    enabled=True,
                    analysis_enabled=True,
                ),
                TargetCountry(
                    country_code="MX",
                    name_cn="墨西哥",
                    name_en="Mexico",
                    region_code="NORTH_AMERICA",
                    continent="North America",
                    default_sort_order=3,
                    enabled=False,
                    analysis_enabled=True,
                ),
                TargetCountry(
                    country_code="DE",
                    name_cn="德国",
                    name_en="Germany",
                    region_code="EUROPE_WEST",
                    continent="Europe",
                    default_sort_order=1,
                    enabled=True,
                    analysis_enabled=False,
                ),
                AnalysisCountryPreset(
                    preset_code="DB_PRESET",
                    name_cn="数据库预设",
                    name_en="Database preset",
                    country_codes=["US", "MX"],
                    region_code="NORTH_AMERICA",
                    is_default=True,
                    sort_order=1,
                    enabled=True,
                ),
            ]
        )
        db.commit()

    default_countries = client.get("/api/markets/countries")
    all_countries = client.get("/api/markets/countries", params={"include_disabled": "true", "analysis_only": "false"})
    presets = client.get("/api/markets/presets", params={"default_only": "true"})

    assert default_countries.status_code == 200
    assert default_countries.json()["source"] == "database"
    assert [item["country_code"] for item in default_countries.json()["items"]] == ["US"]
    assert all_countries.status_code == 200
    assert [item["country_code"] for item in all_countries.json()["items"]] == ["DE", "US", "MX"]
    assert presets.status_code == 200
    assert presets.json()["items"][0]["preset_code"] == "DB_PRESET"


def test_catalog_validation_rejects_unknown_disabled_and_not_analysis_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        db.add_all(
            [
                TargetCountry(
                    country_code="US",
                    name_cn="美国",
                    name_en="United States",
                    region_code="NORTH_AMERICA",
                    enabled=True,
                    analysis_enabled=True,
                ),
                TargetCountry(
                    country_code="MX",
                    name_cn="墨西哥",
                    name_en="Mexico",
                    region_code="NORTH_AMERICA",
                    enabled=False,
                    analysis_enabled=True,
                ),
                TargetCountry(
                    country_code="DE",
                    name_cn="德国",
                    name_en="Germany",
                    region_code="EUROPE_WEST",
                    enabled=True,
                    analysis_enabled=False,
                ),
            ]
        )
        db.commit()

        service = TargetMarketCatalogService(db)

        assert service.validate_analysis_countries(["usa", "US"]) == ["US"]
        with pytest.raises(TargetMarketCatalogError, match="unsupported countries: JP"):
            service.validate_analysis_countries(["JP"])
        with pytest.raises(TargetMarketCatalogError, match="disabled countries: MX"):
            service.validate_analysis_countries(["MX"])
        with pytest.raises(TargetMarketCatalogError, match="countries not enabled for analysis: DE"):
            service.validate_analysis_countries(["DE"])


def test_catalog_validation_caps_at_20_unique_countries(
    session_factory: sessionmaker[Session],
) -> None:
    country_codes = _generated_country_codes(21)
    with session_factory() as db:
        db.add_all(
            [
                TargetCountry(
                    country_code=code,
                    name_cn=code,
                    name_en=code,
                    region_code="TEST",
                    enabled=True,
                    analysis_enabled=True,
                    default_sort_order=index,
                )
                for index, code in enumerate(country_codes, start=1)
            ]
        )
        db.commit()

        service = TargetMarketCatalogService(db)

        assert service.validate_analysis_countries(country_codes[:20] + [country_codes[0]]) == country_codes[:20]
        with pytest.raises(TargetMarketCatalogError, match="at most 20"):
            service.validate_analysis_countries(country_codes)


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


@pytest.fixture()
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    local_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield local_session
    finally:
        Base.metadata.drop_all(bind=engine)


def _generated_country_codes(count: int) -> list[str]:
    codes: list[str] = []
    for first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for second in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            code = f"{first}{second}"
            if code in {"US", "GB", "JP", "AU", "SG"}:
                continue
            codes.append(code)
            if len(codes) == count:
                return codes
    raise AssertionError("not enough generated country codes")
