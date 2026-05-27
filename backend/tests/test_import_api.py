from collections.abc import Generator
import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import CompetitorItem, ProductKeyword
from app.services.importers import csv_importer

_ = _models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"


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


def test_seed_csv_files_exist_with_required_headers_and_rows() -> None:
    expectations = {
        "product_catalog.csv": {
            "min_rows": 10,
            "headers": {
                "product_key",
                "product_name_cn",
                "product_name_en",
                "category",
                "cost_price_cny",
                "weight_kg",
                "package_size",
                "material",
                "certification",
                "moq",
                "keywords",
                "description",
            },
        },
        "competitor_samples.csv": {
            "min_rows": 80,
            "headers": {
                "platform",
                "country",
                "keyword",
                "title",
                "price",
                "currency",
                "rating",
                "review_count",
                "product_url",
                "image_url",
                "collected_at",
            },
        },
        "market_profiles.csv": {
            "min_rows": 5,
            "headers": {
                "country_code",
                "country_name",
                "gdp_per_capita",
                "population",
                "internet_penetration",
                "market_size_level",
                "competition_level",
                "logistics_difficulty",
                "notes",
            },
        },
        "trade_samples.csv": {
            "min_rows": 20,
            "headers": {
                "hs_code",
                "product_category",
                "reporter",
                "partner",
                "year",
                "flow",
                "trade_value_usd",
                "quantity",
                "source",
            },
        },
        "content_trends.csv": {
            "min_rows": 50,
            "headers": {
                "platform",
                "country",
                "keyword",
                "title",
                "url",
                "channel_or_community",
                "published_at",
                "heat_score",
                "summary",
                "content_style",
            },
        },
        "user_discussions.csv": {
            "min_rows": 30,
            "headers": {
                "discussion_id",
                "platform",
                "country",
                "keyword",
                "topic_title",
                "community",
                "discussion_summary",
                "sentiment",
                "pain_point",
                "desired_feature",
                "purchase_intent",
                "interaction_count",
                "published_at",
                "url",
            },
        },
    }

    for file_name, expectation in expectations.items():
        path = SEED_DIR / file_name
        assert path.exists()
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert set(reader.fieldnames or []) >= expectation["headers"]
        assert len(rows) >= expectation["min_rows"]

    with (SEED_DIR / "product_catalog.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        products = {row["product_name_cn"] for row in csv.DictReader(csv_file)}
    assert {
        "宠物凉感垫",
        "波西米亚风毛毯",
        "四件套",
        "儿童枕套",
        "夏凉被",
        "沙发毯",
        "浴巾",
        "防螨枕套",
        "宿舍床品套装",
        "婴儿包被",
    } <= products

    with (SEED_DIR / "competitor_samples.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        competitors = list(csv.DictReader(csv_file))
    assert {
        "eBay",
        "Amazon Sample",
        "Shopee Sample",
        "Temu Sample",
        "Etsy Sample",
        "Rakuten Sample",
    } <= {row["platform"] for row in competitors}

    with (SEED_DIR / "content_trends.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        trends = list(csv.DictReader(csv_file))
    assert {
        "YouTube Sample",
        "TikTok Sample",
        "Pinterest Sample",
        "Reddit Sample",
    } <= {row["platform"] for row in trends}
    assert {
        "home decor",
        "pet cooling mat",
        "boho bedroom",
        "dorm room bedding",
    } <= {row["keyword"] for row in trends}

    with (SEED_DIR / "market_profiles.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        profiles = list(csv.DictReader(csv_file))
    assert {"US", "GB", "JP", "AU", "SG"} == {row["country_code"] for row in profiles}


def test_product_import_requires_company_id(client_with_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _session_factory = client_with_session

    response = client.post("/api/import/products", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["dataset"] == "products"
    assert detail["errors"][0]["field"] == "company_id"
    assert "required" in detail["errors"][0]["message"]


def test_product_import_inserts_products_and_keywords(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _create_company(client)

    response = client.post("/api/import/products", json={"company_id": company_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == "products"
    assert payload["total_rows"] == 10
    assert payload["inserted"] == 10
    assert payload["failed"] == 0
    assert payload["source"] == "csv_fallback"

    products_response = client.get(f"/api/products?company_id={company_id}")
    assert products_response.status_code == 200
    assert products_response.json()["total"] == 10

    with session_factory() as db:
        keyword_count = db.scalar(select(func.count()).select_from(ProductKeyword))
    assert keyword_count and keyword_count >= 30


def test_seed_import_endpoints_insert_market_demo_data(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    expectations = {
        "/api/import/competitors": 84,
        "/api/import/market-profiles": 30,
        "/api/import/trade-samples": 40,
        "/api/import/content-trends": 52,
        "/api/import/user-discussions": 30,
    }

    for endpoint, inserted in expectations.items():
        response = client.post(endpoint)
        assert response.status_code == 200
        payload = response.json()
        assert payload["inserted"] == inserted
        assert payload["failed"] == 0
        assert payload["source"] == "csv_fallback"


def test_validate_mode_does_not_write_rows(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session

    response = client.post("/api/import/competitors", json={"mode": "validate"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "validate"
    assert payload["total_rows"] == 84
    assert payload["valid_rows"] == 84
    assert payload["inserted"] == 0

    with session_factory() as db:
        competitor_count = db.scalar(select(func.count()).select_from(CompetitorItem))
    assert competitor_count == 0


def test_importer_reports_missing_required_headers(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
) -> None:
    _client, session_factory = client_with_session
    (tmp_path / "bad_competitors.csv").write_text(
        "platform,country\n"
        "eBay,US\n",
        encoding="utf-8",
    )

    with session_factory() as db:
        with pytest.raises(csv_importer.CsvImportValidationError) as exc_info:
            csv_importer.import_competitors(
                db,
                file_name="bad_competitors.csv",
                seed_dir=tmp_path,
            )

    result = exc_info.value.result
    assert result.errors[0].field == "header"
    assert "Missing required CSV columns" in result.errors[0].message


def test_importer_reports_invalid_numbers_and_dates(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    tmp_path: Path,
) -> None:
    _client, session_factory = client_with_session
    (tmp_path / "bad_content.csv").write_text(
        "platform,country,keyword,title,url,channel_or_community,published_at,heat_score,summary,content_style\n"
        "YouTube Sample,US,home decor,Bad trend,https://sample.example,bad,not-a-date,hot,summary,review\n",
        encoding="utf-8",
    )

    with session_factory() as db:
        with pytest.raises(csv_importer.CsvImportValidationError) as exc_info:
            csv_importer.import_content_trends(
                db,
                file_name="bad_content.csv",
                seed_dir=tmp_path,
            )

    fields = {error.field for error in exc_info.value.result.errors}
    assert {"published_at", "heat_score"} <= fields


def _create_company(client: TestClient) -> int:
    response = client.post(
        "/api/companies",
        json={
            "name": "Nantong Demo Home Textile",
            "region": "Nantong",
            "industry": "Home textiles",
            "description": "Seed import test company",
            "target_countries": ["US", "GB", "JP", "AU", "SG"],
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])
