from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.db import get_db
from app.db.base import Base
from app.main import app

_ = _models


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
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
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_company_and_product_lists_are_empty_by_default(client: TestClient) -> None:
    companies_response = client.get("/api/companies")
    products_response = client.get("/api/products")

    assert companies_response.status_code == 200
    assert companies_response.json() == {"items": [], "total": 0}
    assert products_response.status_code == 200
    assert products_response.json() == {"items": [], "total": 0}


def test_create_company_and_list_it(client: TestClient) -> None:
    response = client.post(
        "/api/companies",
        json={
            "name": "Jiangsu Sample Manufacturing",
            "region": "Jiangsu",
            "industry": "Smart appliances",
            "description": "Demo manufacturer",
            "target_countries": ["Japan", "Germany"],
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 1
    assert created["name"] == "Jiangsu Sample Manufacturing"
    assert created["target_countries"] == ["Japan", "Germany"]

    list_response = client.get("/api/companies")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]


def test_create_product_for_existing_company(client: TestClient) -> None:
    company_response = client.post(
        "/api/companies",
        json={"name": "Jiangsu Product Company", "region": "Suzhou"},
    )
    company_id = company_response.json()["id"]

    response = client.post(
        "/api/products",
        json={
            "company_id": company_id,
            "product_name_cn": "Smart Thermos",
            "product_name_en": "Smart Thermos Bottle",
            "category": "Consumer goods",
            "cost_price_cny": "49.90",
            "weight_kg": "0.350",
            "package_size": "8x8x24cm",
            "material": "Stainless steel",
            "certification": "CE",
            "moq": 100,
            "description": "Temperature display bottle",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 1
    assert created["company_id"] == company_id
    assert created["product_name_en"] == "Smart Thermos Bottle"

    list_response = client.get(f"/api/products?company_id={company_id}")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]


def test_create_product_for_missing_company_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/products",
        json={
            "company_id": 999,
            "product_name_cn": "Missing Company Product",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}
