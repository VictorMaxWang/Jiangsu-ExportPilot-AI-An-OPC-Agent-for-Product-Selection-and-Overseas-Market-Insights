import asyncio
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.schemas import YoutubeSearchResponse
from app.services.providers.youtube import YoutubeProvider, youtube_seed_queries


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEMO_COUNTRIES = {"US", "GB", "JP", "AU", "SG"}
DEMO_CONTENT_KEYWORDS = {
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


def test_youtube_settings_defaults_key_and_enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_youtube_env(monkeypatch)
    get_settings.cache_clear()
    defaults = get_settings()
    assert defaults.enable_youtube is True
    assert defaults.youtube_data_api_key is None

    monkeypatch.setenv("YOUTUBE_API_KEY", "legacy-fake-key")
    get_settings.cache_clear()
    assert get_settings().youtube_data_api_key is None

    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "youtube-fake-key")
    monkeypatch.setenv("ENABLE_YOUTUBE", "false")
    get_settings.cache_clear()
    configured = get_settings()
    assert configured.youtube_data_api_key == "youtube-fake-key"
    assert configured.enable_youtube is False
    get_settings.cache_clear()


def test_youtube_seed_queries_cover_demo_matrix() -> None:
    queries = set(youtube_seed_queries(SEED_DIR))

    assert len(queries) == 50
    assert queries == {
        (keyword, country)
        for keyword in DEMO_CONTENT_KEYWORDS
        for country in DEMO_COUNTRIES
    }


def test_youtube_search_missing_key_uses_csv_fallback() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"items": []})

    provider = YoutubeProvider(
        settings=Settings(youtube_data_api_key=None, enable_youtube=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_videos("home decor", country="US"))

    assert calls == 0
    assert result.provider == "youtube"
    assert result.keyword == "home decor"
    assert result.country == "US"
    assert result.fallback_used is True
    assert result.items
    assert all(item.platform == "YouTube" for item in result.items)
    assert all(item.source_type == "csv_fallback" for item in result.items)


def test_youtube_search_disabled_uses_csv_fallback_even_with_key() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"items": []})

    provider = YoutubeProvider(
        settings=Settings(youtube_data_api_key="disabled-fake-key", enable_youtube=False),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_videos("pet cooling mat", country="GB"))

    assert calls == 0
    assert result.fallback_used is True
    assert result.items[0].source_type == "csv_fallback"
    assert "disabled-fake-key" not in result.model_dump_json()


def test_youtube_search_parses_mock_response_and_does_not_leak_key() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.params["key"] == "provider-fake-key"
        assert request.url.params["part"] == "snippet"
        assert request.url.params["q"] == "boho bedroom"
        assert request.url.params["type"] == "video"
        assert request.url.params["maxResults"] == "10"
        assert request.url.params["relevanceLanguage"] == "en"
        assert request.url.params["regionCode"] == "US"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": {"videoId": "abc123"},
                        "snippet": {
                            "title": "Boho bedroom textile trend",
                            "channelTitle": "Home Style Studio",
                            "publishedAt": "2026-05-27T12:00:00Z",
                            "description": "Layered neutral bedding ideas.",
                            "thumbnails": {
                                "default": {"url": "https://img.example/default.jpg"},
                                "high": {"url": "https://img.example/high.jpg"},
                            },
                        },
                    }
                ]
            },
        )

    provider = YoutubeProvider(
        settings=Settings(youtube_data_api_key="provider-fake-key", enable_youtube=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_videos("Boho Bedroom", country="us", max_results=20))

    assert result.fallback_used is False
    assert len(result.items) == 1
    item = result.items[0]
    assert item.platform == "YouTube"
    assert item.country == "US"
    assert item.keyword == "boho bedroom"
    assert item.title == "Boho bedroom textile trend"
    assert item.channel_title == "Home Style Studio"
    assert item.thumbnail_url == "https://img.example/high.jpg"
    assert item.video_url == "https://www.youtube.com/watch?v=abc123"
    assert item.source_type == "api"
    assert "provider-fake-key" not in result.model_dump_json()
    assert requests


def test_youtube_search_schema_matches_contract() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": {"videoId": "xyz789"},
                        "snippet": {
                            "title": "Dorm bedding checklist",
                            "channelTitle": "Campus Setup",
                            "publishedAt": "2026-05-27T12:15:00Z",
                        },
                    }
                ]
            },
        )

    provider = YoutubeProvider(
        settings=Settings(youtube_data_api_key="schema-fake-key", enable_youtube=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_videos("dorm room bedding"))

    assert YoutubeSearchResponse.model_validate(result.model_dump()) == result


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_youtube_search_falls_back_on_api_error(status_code: int) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "upstream failure"})

    provider = YoutubeProvider(
        settings=Settings(youtube_data_api_key="error-fake-key", enable_youtube=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_videos("cotton bedding set", country="US"))

    assert result.fallback_used is True
    assert result.items
    assert all(item.source_type == "csv_fallback" for item in result.items)
    assert "error-fake-key" not in result.model_dump_json()


def _clear_youtube_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("YOUTUBE_DATA_API_KEY", "YOUTUBE_API_KEY", "ENABLE_YOUTUBE", "SUPIN_ENABLE_YOUTUBE"):
        monkeypatch.delenv(name, raising=False)
