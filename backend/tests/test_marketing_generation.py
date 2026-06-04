from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AnalysisRun, Company, OpportunityScore, Product
from app.services.ai import BailianChatCompletion


def test_marketing_generate_returns_exact_contract(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    stub = StubBailianClient(_valid_marketing_json())
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            "/api/marketing/generate",
            json={
                "product": "Boho Throw Blanket",
                "country": "US",
                "target_users": ["Apartment renters"],
                "selling_points": ["Soft acrylic cotton blend"],
                "price_range": "$24.99-$39.99",
                "content_themes": ["room makeover"],
                "risk_notes": ["Sample data analysis only."],
            },
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "title",
        "bullet_points",
        "seo_keywords",
        "short_video_script",
        "pinterest_keywords",
        "platform_listing_advice",
        "risk_notes",
    }
    assert payload["title"] == "Boho Throw Blanket for Cozy Apartment Styling"
    assert len(payload["bullet_points"]) == 5
    assert stub.json_mode is True
    assert "sales forecast" in stub.messages[0]["content"]
    user_payload = json.loads(stub.messages[-1]["content"])
    assert user_payload["product"] == "Boho Throw Blanket"
    assert user_payload["country"] == "US"


def test_marketing_generate_missing_key_returns_sanitized_503(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_bailian_env(monkeypatch)
    get_settings.cache_clear()
    client, _session_factory = client_with_session

    response = client.post(
        "/api/marketing/generate",
        json={"product": "Boho Throw Blanket", "country": "US"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "BAILIAN_NOT_CONFIGURED"
    assert payload["detail"]["message"] == "Bailian is not configured on the backend. Set DASHSCOPE_API_KEY."
    response_text = response.text.lower()
    assert "authorization" not in response_text
    assert "bearer" not in response_text
    get_settings.cache_clear()


def test_marketing_generate_rejects_policy_violating_output(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session
    unsafe_payload = _valid_marketing_payload() | {"title": "Guaranteed conversion sales forecast bundle"}
    stub = StubBailianClient(json.dumps(unsafe_payload))
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            "/api/marketing/generate",
            json={"product": "Boho Throw Blanket", "country": "US"},
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AI_RESPONSE_SCHEMA_ERROR"


def test_marketing_generate_qwen_timeout_returns_504(
    monkeypatch: pytest.MonkeyPatch,
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    monkeypatch.setenv("BAILIAN_TIMEOUT_SECONDS", "0.01")
    get_settings.cache_clear()
    client, _session_factory = client_with_session
    app.dependency_overrides[get_bailian_client] = lambda: SlowBailianClient()
    try:
        response = client.post(
            "/api/marketing/generate",
            json={"product": "Boho Throw Blanket", "country": "US"},
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)
        get_settings.cache_clear()

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "AI_RESPONSE_TIMEOUT"


def test_marketing_generate_persists_to_analysis_workflow_state(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id, score_id = _seed_analysis(session_factory)
    stub = StubBailianClient(_valid_marketing_json())
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            "/api/marketing/generate",
            json={
                "product": "Boho Throw Blanket",
                "country": "US",
                "analysis_id": analysis_id,
                "score_id": score_id,
                "persist_to_analysis": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    with session_factory() as db:
        analysis_run = db.get(AnalysisRun, analysis_id)
        assert analysis_run is not None
        assets = (analysis_run.workflow_state or {}).get("marketing_assets")
        assert isinstance(assets, list)
        assert len(assets) == 1
        assert assets[0]["title"] == "Boho Throw Blanket for Cozy Apartment Styling"
        assert assets[0]["score_id"] == score_id


def test_marketing_generate_score_country_mismatch_returns_422(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    analysis_id, score_id = _seed_analysis(session_factory)
    stub = StubBailianClient(_valid_marketing_json())
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            "/api/marketing/generate",
            json={
                "product": "Boho Throw Blanket",
                "country": "JP",
                "analysis_id": analysis_id,
                "score_id": score_id,
            },
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCORE_COUNTRY_MISMATCH"


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
    app.dependency_overrides.pop(get_bailian_client, None)
    Base.metadata.drop_all(bind=engine)


class StubBailianClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, str]] = []
        self.json_mode = False

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> BailianChatCompletion:
        self.messages = messages
        self.json_mode = json_mode
        return BailianChatCompletion(content=self.content, model="qwen3.6-plus")


class SlowBailianClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        await asyncio.sleep(0.05)
        return BailianChatCompletion(content=_valid_marketing_json(), model="qwen3.6-plus")


def _seed_analysis(session_factory: sessionmaker[Session]) -> tuple[int, int]:
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
        db.flush()
        analysis_run = AnalysisRun(
            company_id=company.id,
            status="completed",
            input_products=[],
            target_countries=["US"],
            workflow_state={"marketing_assets": []},
        )
        db.add(analysis_run)
        db.flush()
        score = OpportunityScore(
            analysis_id=analysis_run.id,
            product_id=product.id,
            country="US",
            total_score=Decimal("78.50"),
            rank=1,
            reason="Market opportunity is supported by content direction and competitor context.",
            risk="Sample data analysis should be verified before publishing.",
            next_action="Run a small content test and review platform claim rules.",
            fallback_used=False,
            ai_fallback_used=False,
            sources=[],
            evidence={"keyword": "boho throw blanket", "content_fallback_used": True},
            competitor_analysis={"price_suggestion": "Validate the landed price band."},
        )
        db.add(score)
        db.commit()
        return analysis_run.id, score.id


def _valid_marketing_json() -> str:
    return json.dumps(_valid_marketing_payload())


def _valid_marketing_payload() -> dict[str, object]:
    return {
        "title": "Boho Throw Blanket for Cozy Apartment Styling",
        "bullet_points": [
            "Soft acrylic cotton blend designed for sofa, bedroom, and gift styling.",
            "Boho texture works with neutral rooms, dorm spaces, and seasonal refreshes.",
            "Lightweight throw format keeps storage and cross-border shipping practical.",
            "Clear material and care details help buyers compare before purchase.",
            "Use lifestyle photos to show scale, texture, and everyday home scenarios.",
        ],
        "seo_keywords": ["boho throw blanket", "apartment decor blanket"],
        "short_video_script": "Open with a plain sofa, add the throw, show texture closeups, then end with care and size details.",
        "pinterest_keywords": ["boho bedroom throw", "cozy apartment styling"],
        "platform_listing_advice": "Publish as a draft for review, verify care claims, and keep sample data limitations in the report.",
        "risk_notes": ["Treat this as content direction from sample data analysis and verify claims before publishing."],
    }


def _clear_bailian_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DASHSCOPE_API_KEY",
        "BAILIAN_API_KEY",
        "SUPIN_DASHSCOPE_API_KEY",
        "SUPIN_BAILIAN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
