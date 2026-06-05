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
from app.models import AnalysisCountryPreset, CompetitorItem, ProductKeyword, TargetCountry
from app.services.importers import csv_importer

_ = _models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEMO_COUNTRIES = {"US", "GB", "JP", "AU", "SG"}
CATALOG_COUNTRIES = {
    "JP",
    "KR",
    "SG",
    "MY",
    "AE",
    "GB",
    "DE",
    "FR",
    "NL",
    "IT",
    "US",
    "CA",
    "MX",
    "BR",
    "CL",
    "AU",
    "NZ",
    "ZA",
    "EG",
}
COUNTRY_PRESETS = {
    "FIVE_CONTINENT_REPS": ["JP", "DE", "US", "AU", "ZA"],
    "MATURE_WESTERN_MARKETS": ["US", "CA", "GB", "DE", "FR", "NL", "IT"],
    "EAST_AND_SEA": ["JP", "KR", "SG", "MY"],
    "BELT_ROAD_POTENTIAL": ["MY", "AE", "EG", "ZA"],
}
COMPETITOR_PLATFORMS = {
    "Etsy Sample",
    "Amazon Sample",
    "eBay Sample",
    "Rakuten Sample",
    "Shopee Sample",
    "Temu Sample",
}
COMPETITOR_KEYWORDS = {
    "pet cooling mat",
    "boho blanket",
    "duvet cover",
    "kids pillowcase",
    "summer quilt",
    "sofa throw blanket",
    "bath towel",
    "anti mite pillowcase",
    "dorm room bedding",
    "baby swaddle blanket",
}
CONTENT_PLATFORMS = {
    "GDELT Sample",
    "YouTube Sample",
    "TikTok Sample",
    "Pinterest Sample",
    "Reddit Sample",
}
CONTENT_KEYWORDS = {
    "bedroom makeover",
    "home decor",
    "pet summer care",
    "dorm room essentials",
    "boho bedroom",
    "cozy room",
    "anti allergy bedding",
    "baby nursery",
    "dorm room bedding",
    "pet cooling mat",
}
TRADE_YEARS = {"2020", "2021", "2022", "2023", "2024"}
TRADE_CATEGORIES = {
    "Cotton bed linen",
    "Blankets and travelling rugs",
    "Toilet and kitchen linen",
    "Bedding articles and cushions",
}


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
            "exact_rows": 300,
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
            "min_rows": 19,
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
        "target_countries.csv": {
            "exact_rows": 19,
            "headers": {
                "country_code",
                "name_cn",
                "name_en",
                "region_code",
                "region_name_cn",
                "region_name_en",
                "continent",
                "currency_code",
                "languages",
                "default_sort_order",
                "enabled",
                "analysis_enabled",
                "disabled_reason",
                "provider_mappings",
                "fallback_enabled",
                "notes",
            },
        },
        "analysis_country_presets.csv": {
            "exact_rows": 4,
            "headers": {
                "preset_code",
                "name_cn",
                "name_en",
                "description",
                "country_codes",
                "industry_tags",
                "region_code",
                "is_default",
                "sort_order",
                "enabled",
            },
        },
        "trade_samples.csv": {
            "exact_rows": 100,
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
            "exact_rows": 250,
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
            "exact_rows": 100,
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
        if "exact_rows" in expectation:
            assert len(rows) == expectation["exact_rows"]
        else:
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
    assert COMPETITOR_PLATFORMS == {row["platform"] for row in competitors}
    assert DEMO_COUNTRIES == {row["country"] for row in competitors}
    assert COMPETITOR_KEYWORDS == {row["keyword"] for row in competitors}
    assert all(row["product_url"].startswith("https://sample.example/") for row in competitors)
    assert all(row["image_url"].startswith("https://sample.example/") for row in competitors)

    with (SEED_DIR / "content_trends.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        trends = list(csv.DictReader(csv_file))
    assert CONTENT_PLATFORMS == {row["platform"] for row in trends}
    assert DEMO_COUNTRIES == {row["country"] for row in trends}
    assert CONTENT_KEYWORDS == {row["keyword"] for row in trends}
    assert all(row["url"].startswith("https://sample.example/") for row in trends)

    with (SEED_DIR / "trade_samples.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        trade_rows = list(csv.DictReader(csv_file))
    trade_keys = {
        (row["reporter"], row["partner"], row["hs_code"], row["year"], row["flow"])
        for row in trade_rows
    }
    assert DEMO_COUNTRIES == {row["reporter"] for row in trade_rows}
    assert TRADE_YEARS == {row["year"] for row in trade_rows}
    assert TRADE_CATEGORIES == {row["product_category"] for row in trade_rows}
    assert len(trade_keys) == 100
    assert {row["partner"] for row in trade_rows} == {"China"}
    assert {row["flow"] for row in trade_rows} == {"Import"}
    assert {row["source"] for row in trade_rows} == {"UN Comtrade Sample"}

    with (SEED_DIR / "user_discussions.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        discussions = list(csv.DictReader(csv_file))
    assert {row["discussion_id"] for row in discussions} == {f"UD{index:03d}" for index in range(1, 101)}
    assert DEMO_COUNTRIES == {row["country"] for row in discussions}
    assert COMPETITOR_KEYWORDS == {row["keyword"] for row in discussions}
    assert all(row["url"].startswith("https://sample.example/") for row in discussions)

    with (SEED_DIR / "market_profiles.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        profiles = list(csv.DictReader(csv_file))
    assert CATALOG_COUNTRIES == {row["country_code"] for row in profiles}

    with (SEED_DIR / "target_countries.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        countries = list(csv.DictReader(csv_file))
    assert CATALOG_COUNTRIES == {row["country_code"] for row in countries}
    assert all(row["enabled"] == "true" and row["analysis_enabled"] == "true" for row in countries)
    assert all(row["provider_mappings"].startswith("{") for row in countries)

    with (SEED_DIR / "analysis_country_presets.csv").open("r", encoding="utf-8-sig", newline="") as csv_file:
        presets = list(csv.DictReader(csv_file))
    assert COUNTRY_PRESETS == {
        row["preset_code"]: [code for code in row["country_codes"].split(";") if code]
        for row in presets
    }


def test_product_import_requires_company_id(client_with_session: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _session_factory = client_with_session

    response = client.post("/api/import/products", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["dataset"] == "products"
    assert detail["errors"][0]["field"] == "company_id"
    assert "required" in detail["errors"][0]["message"]

    alias_response = client.post("/api/products/import", json={})
    assert alias_response.status_code == 422
    assert alias_response.json()["detail"]["errors"][0]["field"] == "company_id"


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


def test_product_import_alias_validate_mode_does_not_write_products(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _create_company(client)

    response = client.post("/api/products/import", json={"company_id": company_id, "mode": "validate"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "validate"
    assert payload["total_rows"] == 10
    assert payload["valid_rows"] == 10
    assert payload["inserted"] == 0

    with session_factory() as db:
        product_count = db.scalar(select(func.count()).select_from(_models.Product))
    assert product_count == 0


def test_product_import_alias_accepts_uploaded_csv(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    company_id = _create_company(client)
    csv_body = (
        "product_key,product_name_cn,product_name_en,category,cost_price_cny,weight_kg,"
        "package_size,material,certification,moq,keywords,description\n"
        "UP001,上传样品,Uploaded Sample,Home Textile,12.30,0.450,20x20x2cm,Cotton,OEKO-TEX,50,"
        "uploaded sample;home textile,Uploaded CSV row\n"
    )

    response = client.post(
        "/api/products/import",
        data={"company_id": str(company_id), "mode": "insert"},
        files={"file": ("uploaded_products.csv", csv_body.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_name"] == "uploaded_products.csv"
    assert payload["inserted"] == 1
    products_response = client.get(f"/api/products?company_id={company_id}")
    assert products_response.json()["total"] == 1


def test_product_import_alias_reports_uploaded_csv_errors(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    company_id = _create_company(client)
    csv_body = (
        "product_key,product_name_cn,product_name_en,category,cost_price_cny,weight_kg,"
        "package_size,material,certification,moq,keywords,description\n"
        "UP002,坏数字,Bad Numbers,Home Textile,not-a-number,0.450,20x20x2cm,Cotton,OEKO-TEX,not-int,"
        "bad sample,Bad CSV row\n"
    )

    response = client.post(
        "/api/products/import",
        data={"company_id": str(company_id), "mode": "insert"},
        files={"file": ("bad_products.csv", csv_body.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["detail"]["errors"]}
    assert {"cost_price_cny", "moq"} <= fields


def test_seed_import_endpoints_insert_market_demo_data(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    expectations = {
        "/api/import/competitors": 300,
        "/api/import/market-profiles": 114,
        "/api/import/target-countries": 19,
        "/api/import/analysis-country-presets": 4,
        "/api/import/trade-samples": 100,
        "/api/import/content-trends": 250,
        "/api/import/user-discussions": 100,
    }

    for endpoint, inserted in expectations.items():
        response = client.post(endpoint)
        assert response.status_code == 200
        payload = response.json()
        assert payload["inserted"] == inserted
        assert payload["failed"] == 0
        assert payload["source"] == "csv_fallback"

    with _session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TargetCountry)) == 19
        assert db.scalar(select(func.count()).select_from(AnalysisCountryPreset)) == 4


def test_validate_mode_does_not_write_rows(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session

    response = client.post("/api/import/competitors", json={"mode": "validate"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "validate"
    assert payload["total_rows"] == 300
    assert payload["valid_rows"] == 300
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
