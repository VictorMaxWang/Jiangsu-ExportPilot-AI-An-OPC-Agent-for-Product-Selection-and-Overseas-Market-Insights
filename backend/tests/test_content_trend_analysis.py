import asyncio
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.trends import get_content_trend_analysis_service
from app.db.base import Base
from app.main import app
from app.models import ApiCallLog, DataSourceCache
from app.schemas import AnalysisSource, ContentTrendAnalysisResponse, ContentTrendSourceItem
from app.services.ai import BailianChatCompletion
from app.services.analysis import ContentTrendAnalysisService
from app.services.data_sources import DataSourceService


def test_content_trend_analysis_falls_back_to_csv_samples_and_discussions(db_session: Session) -> None:
    service = _analysis_service(db_session)

    result = asyncio.run(service.analyze("home decor", "US"))

    assert result.keyword == "home decor"
    assert result.country == "US"
    assert result.fallback_used is True
    assert result.ai_fallback_used is True
    assert result.content_themes
    assert result.marketing_angles
    assert result.pain_points
    assert result.video_script_ideas
    assert result.pinterest_keywords
    assert result.risk_notes
    assert any(item.platform == "Pinterest Sample" for item in result.source_items)
    assert any(item.platform == "TikTok Sample" for item in result.source_items)
    for item in result.source_items:
        if item.platform in {"TikTok Sample", "Pinterest Sample"}:
            assert item.source_type == "csv_fallback"
            assert item.api_invoked is False
            assert item.sample_notice is not None

    providers = set(db_session.scalars(select(ApiCallLog.provider))) | set(db_session.scalars(select(DataSourceCache.provider)))
    assert "tiktok" not in providers
    assert "pinterest" not in providers


def test_content_trend_api_route_maps_to_analysis_service() -> None:
    stub = StubContentTrendAnalysisService()
    app.dependency_overrides[get_content_trend_analysis_service] = lambda: stub
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/trends/content/analyze",
                json={"keyword": "home decor", "country": "US"},
            )
    finally:
        app.dependency_overrides.pop(get_content_trend_analysis_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["keyword"] == "home decor"
    assert payload["content_themes"] == ["room makeover"]
    assert stub.calls == [("analyze", "home decor", "US")]


class FailingYoutubeProvider:
    async def search_videos(
        self,
        _keyword: str,
        country: str = "US",
        max_results: int = 10,
    ) -> object:
        raise RuntimeError("youtube unavailable")


class FailingGdeltProvider:
    async def search(
        self,
        _query: str,
        *,
        country: str | None = None,
        max_records: int = 10,
    ) -> object:
        raise RuntimeError("gdelt unavailable")


class BadJsonAiClient:
    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        return BailianChatCompletion(content="not json", model="qwen3.6-plus")


class StubContentTrendAnalysisService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def analyze(self, keyword: str, country: str) -> ContentTrendAnalysisResponse:
        self.calls.append(("analyze", keyword, country))
        return ContentTrendAnalysisResponse(
            keyword=keyword,
            country=country,
            content_themes=["room makeover"],
            marketing_angles=["Show compact room styling."],
            pain_points=["Small room storage is hard."],
            video_script_ideas=["Before and after room styling."],
            pinterest_keywords=["home decor ideas"],
            risk_notes=["Pinterest is CSV sample only."],
            source_items=[
                ContentTrendSourceItem(
                    platform="Pinterest Sample",
                    country=country,
                    keyword=keyword,
                    title="Sample pin",
                    heat_score=Decimal("80"),
                    source_type="csv_fallback",
                    source_label="CSV fallback: Pinterest Sample",
                    api_invoked=False,
                    fallback_used=True,
                )
            ],
            fallback_used=True,
            ai_fallback_used=True,
            sources=[
                AnalysisSource(
                    provider="csv_pinterest_sample",
                    source_label="CSV fallback: Pinterest Sample",
                    source_type="csv_fallback",
                    fallback_used=True,
                    api_invoked=False,
                )
            ],
        )


def _analysis_service(db: Session) -> ContentTrendAnalysisService:
    data_sources = DataSourceService(
        db,
        youtube_provider=FailingYoutubeProvider(),
        gdelt_provider=FailingGdeltProvider(),
    )
    return ContentTrendAnalysisService(data_sources, ai_client=BadJsonAiClient())


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
