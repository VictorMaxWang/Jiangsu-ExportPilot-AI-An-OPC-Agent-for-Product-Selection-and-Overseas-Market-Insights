from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AnalysisRun, Company, OpportunityScore, Product


def test_dashboard_api_returns_aggregated_market_view(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_dashboard_run(session_factory, include_workflow_state=True)

    response = client.get(f"/api/dashboard/{analysis_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_id"] == analysis_id
    assert len(payload["product_scores"]) == 2
    assert payload["product_scores"][0]["country"] == "US"
    assert float(payload["product_scores"][0]["total_score"]) > 0
    assert payload["country_scores"][0]["country"] == "US"
    assert payload["price_ranges"][0]["currency"] == "USD"
    assert "不代表真实销量" in payload["price_ranges"][0]["sample_notice"]
    assert payload["content_themes"][0]["theme"] == "giftable home textile"
    assert payload["top_recommendations"][0]["next_action"]
    assert any(card["source"] == "data_lineage" for card in payload["risk_cards"])
    assert any(source["provider"] == "etsy" for source in payload["data_sources_used"])


def test_dashboard_api_returns_empty_arrays_for_run_without_scores(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_empty_analysis_run(session_factory)

    response = client.get(f"/api/dashboard/{analysis_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_id"] == analysis_id
    assert payload["product_scores"] == []
    assert payload["country_scores"] == []
    assert payload["price_ranges"] == []
    assert payload["content_themes"] == []
    assert payload["top_recommendations"] == []
    assert payload["risk_cards"] == []


def test_dashboard_api_returns_404_for_unknown_analysis(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    response = client.get("/api/dashboard/99999")

    assert response.status_code == 404


def test_dashboard_api_supports_scoring_only_runs(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id = _seed_dashboard_run(session_factory, include_workflow_state=False)

    response = client.get(f"/api/dashboard/{analysis_id}")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["product_scores"]) == 2
    assert payload["content_themes"] == []
    assert payload["data_sources_used"]


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


def _seed_empty_analysis_run(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        company = Company(name="Jiangsu Empty Co", region="Jiangsu", industry="Home Textile")
        db.add(company)
        db.flush()
        analysis_run = AnalysisRun(
            company_id=company.id,
            status="running",
            input_products=[],
            target_countries=["US"],
            workflow_state={},
        )
        db.add(analysis_run)
        db.commit()
        return analysis_run.id


def _seed_dashboard_run(session_factory: sessionmaker[Session], *, include_workflow_state: bool) -> int:
    with session_factory() as db:
        company = Company(name="Jiangsu Demo Co", region="Jiangsu", industry="Home Textile")
        db.add(company)
        db.flush()
        product = Product(
            company_id=company.id,
            product_name_cn="样本盖毯",
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
        db.flush()
        workflow_state = (
            {
                "content_trends": [
                    {
                        "product_id": product.id,
                        "country": "US",
                        "keyword": "boho throw blanket",
                        "content_themes": ["giftable home textile", "giftable home textile", "small apartment decor"],
                        "source_item_count": 6,
                    }
                ],
                "provider_breakdown": [
                    {
                        "provider": "worldbank",
                        "source_types": ["api"],
                        "labels": ["World Bank market profile"],
                        "api_invoked": True,
                        "fallback_used": False,
                    }
                ],
                "provider_sources": [
                    {
                        "provider": "gdelt",
                        "source_label": "Unified content trends",
                        "source_type": "csv_fallback",
                        "fallback_used": True,
                        "api_invoked": False,
                        "detail": "Content trends include fallback rows.",
                    }
                ],
            }
            if include_workflow_state
            else {}
        )
        analysis_run = AnalysisRun(
            company_id=company.id,
            status="fallback_used",
            input_products=[
                {
                    "id": product.id,
                    "product_name_cn": product.product_name_cn,
                    "product_name_en": product.product_name_en,
                }
            ],
            target_countries=["US", "JP"],
            step_logs=[
                {
                    "step_id": "03_data_collection",
                    "node": "DataCollectionAgent",
                    "title": "Data collection",
                    "status": "fallback_used",
                    "sources": [
                        {
                            "provider": "un_comtrade",
                            "source_label": "CSV fallback: trade_samples.csv",
                            "source_type": "csv_fallback",
                            "fallback_used": True,
                            "api_invoked": False,
                        }
                    ],
                }
            ],
            workflow_state=workflow_state,
        )
        db.add(analysis_run)
        db.flush()
        db.add_all(
            [
                _score_row(
                    analysis_id=analysis_run.id,
                    product_id=product.id,
                    country="US",
                    rank=1,
                    total_score=Decimal("84.25"),
                    fallback_used=True,
                ),
                _score_row(
                    analysis_id=analysis_run.id,
                    product_id=product.id,
                    country="JP",
                    rank=2,
                    total_score=Decimal("76.50"),
                    fallback_used=False,
                ),
            ]
        )
        db.commit()
        return analysis_run.id


def _score_row(
    *,
    analysis_id: int,
    product_id: int,
    country: str,
    rank: int,
    total_score: Decimal,
    fallback_used: bool,
) -> OpportunityScore:
    return OpportunityScore(
        analysis_id=analysis_id,
        product_id=product_id,
        country=country,
        trend_score=Decimal("80.00"),
        price_score=Decimal("78.00"),
        market_score=Decimal("82.00"),
        supply_score=Decimal("88.00"),
        logistics_score=Decimal("72.00"),
        content_score=Decimal("69.00"),
        total_score=total_score,
        rank=rank,
        reason=f"{country} has a strong opportunity score for the sample product.",
        risk="Validate price band and certification claims before paid launch.",
        next_action="Run a small localized listing test with conservative claims.",
        fallback_used=fallback_used,
        ai_fallback_used=fallback_used,
        sources=[
            {
                "provider": "etsy",
                "source_label": "CSV fallback: competitor_samples.csv" if fallback_used else "Etsy API",
                "source_type": "csv_fallback" if fallback_used else "api",
                "fallback_used": fallback_used,
                "api_invoked": not fallback_used,
                "detail": "Competitor rows are used for price range only.",
            }
        ],
        evidence={"keyword": "boho throw blanket"},
        competitor_analysis={
            "keyword": "boho throw blanket",
            "country": country,
            "item_count": 12,
            "min_price": "12.00",
            "median_price": "24.00",
            "max_price": "42.00",
            "avg_price": "25.50",
            "currency": "USD" if country == "US" else "JPY",
            "common_terms": ["boho", "gift", "home"],
            "competition_level": "high" if country == "US" else "medium",
            "price_suggestion": "Use the lower-middle band for an entry test.",
            "summary": "Competitor sample rows show a directional price band.",
        },
    )
