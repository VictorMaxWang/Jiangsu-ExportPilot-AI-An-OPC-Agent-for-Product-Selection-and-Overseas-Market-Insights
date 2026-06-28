from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.scoring import get_opportunity_scoring_service
from app.db.base import Base
from app.main import app
from app.models import Company, OpportunityScore, Product
from app.services.ai import BailianChatCompletion
from app.services.data_sources import DataSourceService
from app.services.scoring import OpportunityScoringService


def test_scoring_run_persists_ranked_results(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id, product_id = _seed_product(session_factory)

    run_response = client.post(
        "/api/scoring/run",
        json={"company_id": company_id, "product_ids": [product_id], "target_countries": ["US", "GB"]},
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["provider"] == "opportunity_scoring"
    assert payload["status"] == "completed"
    assert payload["item_count"] == 2
    assert [item["rank"] for item in payload["items"]] == [1, 2]
    assert all(0 <= float(item["total_score"]) <= 100 for item in payload["items"])

    analysis_id = payload["analysis_id"]
    results_response = client.get(f"/api/scoring/results/{analysis_id}")

    assert results_response.status_code == 200
    results = results_response.json()
    assert results["analysis_id"] == analysis_id
    assert results["item_count"] == 2
    assert [item["rank"] for item in results["items"]] == [1, 2]
    with session_factory() as db:
        count = db.scalar(select(func.count()).select_from(OpportunityScore))
    assert count == 2


def test_scoring_results_returns_404_for_unknown_analysis(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    response = client.get("/api/scoring/results/99999")

    assert response.status_code == 404


def test_scoring_run_rejects_unknown_product_ids_mixed_with_valid_ids(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id, product_id = _seed_product(session_factory)

    response = client.post(
        "/api/scoring/run",
        json={"company_id": company_id, "product_ids": [product_id, 99999], "target_countries": ["US"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_SCORING_INPUT"
    assert "not found" in response.json()["detail"]["message"].lower()


@pytest.fixture()
def client_with_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_scoring_service() -> Generator[OpportunityScoringService, None, None]:
        db = testing_session_local()
        try:
            data_sources = DataSourceService(
                db,
                worldbank_provider=FailingWorldBankProvider(),
                un_comtrade_provider=FailingUnComtradeProvider(),
                youtube_provider=FailingYoutubeProvider(),
                gdelt_provider=FailingGdeltProvider(),
                etsy_provider=FailingEtsyProvider(),
            )
            yield OpportunityScoringService(db, data_sources, ai_client=BadJsonAiClient())
        finally:
            db.close()

    app.dependency_overrides[get_opportunity_scoring_service] = override_scoring_service
    with TestClient(app) as test_client:
        yield test_client, testing_session_local
    app.dependency_overrides.clear()
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
