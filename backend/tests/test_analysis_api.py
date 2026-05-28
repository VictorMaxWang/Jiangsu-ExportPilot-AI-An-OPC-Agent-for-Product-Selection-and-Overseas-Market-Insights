from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.analysis import get_analysis_background_runner
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import Company, Product
from app.services.agents import ExportInsightWorkflow
from app.services.ai import BailianChatCompletion
from app.services.data_sources import DataSourceService


def test_analysis_api_starts_background_workflow_and_returns_pollable_status(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id, product_id = _seed_product(session_factory)

    start_response = client.post(
        "/api/analysis/run",
        json={"company_id": company_id, "product_ids": [product_id], "target_countries": ["US", "GB"]},
    )

    assert start_response.status_code == 202
    started = start_response.json()
    analysis_id = started["analysis_id"]
    assert started["status_url"] == f"/api/analysis/{analysis_id}/status"

    status_response = client.get(f"/api/analysis/{analysis_id}/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "fallback_used"
    assert status_payload["current_step"] == "09_report_prep"
    assert len(status_payload["step_logs"]) == 9
    assert status_payload["scoring_summary"]["item_count"] == 2
    assert {"ebay", "rakuten", "reddit"}.isdisjoint(status_payload["used_providers"])
    assert status_payload["next_page_url"] == f"/reports?analysis_id={analysis_id}"

    detail_response = client.get(f"/api/analysis/{analysis_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert len(detail_payload["scores"]) == 2
    assert len(detail_payload["reports"]) == 1
    assert detail_payload["marketing_assets"]


def test_analysis_api_returns_404_for_unknown_analysis(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    response = client.get("/api/analysis/99999/status")

    assert response.status_code == 404


def test_analysis_api_returns_404_for_missing_company(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    response = client.post(
        "/api/analysis/run",
        json={"company_id": 99999, "product_ids": [1], "target_countries": ["US"]},
    )

    assert response.status_code == 404


def test_analysis_api_returns_422_for_missing_products(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)

    response = client.post(
        "/api/analysis/run",
        json={"company_id": company_id, "product_ids": [99999], "target_countries": ["US"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_ANALYSIS_INPUT"


def test_analysis_api_validates_product_ids_and_countries(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id, product_id = _seed_product(session_factory)

    empty_products = client.post(
        "/api/analysis/run",
        json={"company_id": company_id, "product_ids": [], "target_countries": ["US"]},
    )
    bad_country = client.post(
        "/api/analysis/run",
        json={"company_id": company_id, "product_ids": [product_id], "target_countries": ["United States"]},
    )

    assert empty_products.status_code == 422
    assert bad_country.status_code == 422


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

    def override_background_runner() -> Callable[[int], Awaitable[None]]:
        async def runner(analysis_id: int) -> None:
            db = testing_session_local()
            try:
                workflow = ExportInsightWorkflow(
                    db,
                    _failing_data_source_service(db),
                    ai_client=BadJsonAiClient(),
                )
                await workflow.run(analysis_id)
            finally:
                db.close()

        return runner

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_analysis_background_runner] = override_background_runner
    with TestClient(app) as test_client:
        yield test_client, testing_session_local
    app.dependency_overrides.pop(get_analysis_background_runner, None)
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


class FailingWorldBankProvider:
    async def fetch_country(self, _country_code: str) -> object:
        raise RuntimeError("worldbank unavailable")


class FailingUnComtradeProvider:
    async def get_trade_flow(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("un comtrade unavailable")


class FailingYoutubeProvider:
    async def search_videos(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("youtube unavailable")


class FailingGdeltProvider:
    async def search(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("gdelt unavailable")


class FailingEtsyProvider:
    async def search_listings(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("etsy unavailable")


class BadJsonAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        return BailianChatCompletion(content="not json", model="qwen3.6-plus")


def _failing_data_source_service(db: Session) -> DataSourceService:
    return DataSourceService(
        db,
        worldbank_provider=FailingWorldBankProvider(),
        un_comtrade_provider=FailingUnComtradeProvider(),
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
        etsy_provider=FailingEtsyProvider(),
    )


def _seed_company(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        company = Company(name="Jiangsu Empty Co", region="Jiangsu", industry="Home Textile")
        db.add(company)
        db.commit()
        return company.id


def _seed_product(session_factory: sessionmaker[Session]) -> tuple[int, int]:
    with session_factory() as db:
        company = Company(name="Jiangsu Demo Co", region="Jiangsu", industry="Home Textile")
        db.add(company)
        db.flush()
        product = Product(
            company_id=company.id,
            product_name_cn="Boho blanket sample",
            product_name_en="Boho Throw Blanket",
            category="Home Textile",
            cost_price_cny=Decimal("42.00"),
            weight_kg=Decimal("0.90"),
            package_size="35x28x12cm",
            material="Acrylic cotton blend",
            certification="OEKO-TEX",
            moq=120,
            description="Soft bohemian style throw blanket for sofa bedroom and gift sets",
        )
        db.add(product)
        db.commit()
        return company.id, product.id
