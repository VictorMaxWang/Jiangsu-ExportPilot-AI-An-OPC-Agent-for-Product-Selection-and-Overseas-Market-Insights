import asyncio
from pathlib import Path

import httpx
import pytest

from app.schemas import GdeltSearchResponse
from app.services.providers import DataProviderValidationError
from app.services.providers.gdelt import GdeltProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"


def test_gdelt_search_no_key_and_normalizes_articles() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "api_key" not in request.url.params
        assert "key" not in request.url.params
        assert "sourcecountry" not in request.url.params
        assert '"boho bedroom"' in request.url.params["query"]
        assert "sourcecountry:unitedkingdom" in request.url.params["query"]
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "title": "Boho bedroom textile trend",
                        "url": "https://news.example/articles/boho-bedroom",
                        "domain": "news.example",
                        "seendate": "20260527T120000Z",
                        "language": "English",
                    }
                ]
            },
        )

    provider = GdeltProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.search("Boho Bedroom", country="gb"))

    assert result.provider == "gdelt"
    assert result.query == "boho bedroom"
    assert result.fallback_used is False
    assert len(result.items) == 1
    item = result.items[0]
    assert item.title == "Boho bedroom textile trend"
    assert item.domain == "news.example"
    assert item.published_at == "2026-05-27T12:00:00+00:00"
    assert item.language == "English"
    assert item.source == "api"
    assert requests


def test_gdelt_search_schema_matches_contract() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "title": "Dorm bedding coverage",
                        "url": "https://news.example/articles/dorm",
                        "seendate": "20260527T121500Z",
                    }
                ]
            },
        )

    provider = GdeltProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.search("dorm room bedding"))

    assert GdeltSearchResponse.model_validate(result.model_dump()) == result
    assert result.items[0].domain == "news.example"


def test_gdelt_search_falls_back_to_content_trends_on_api_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = GdeltProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.search("boho bedroom", country="US"))

    assert result.fallback_used is True
    assert result.query == "boho bedroom"
    assert result.items
    assert all(item.source == "csv_fallback" for item in result.items)
    assert all(item.language == "und" for item in result.items)
    assert all(item.domain == "sample.example" for item in result.items)


def test_gdelt_search_rejects_unsupported_query() -> None:
    provider = GdeltProvider(seed_dir=SEED_DIR)

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.search("unknown product trend"))
