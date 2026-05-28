import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.schemas import EtsySearchResponse
from app.services.providers import DataProviderValidationError
from app.services.providers.etsy import EtsyProvider, etsy_seed_queries


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEMO_COUNTRIES = {"US", "GB", "JP", "AU", "SG"}
DEMO_COMPETITOR_KEYWORDS = {
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


def test_etsy_settings_defaults_key_and_enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_etsy_env(monkeypatch)
    get_settings.cache_clear()
    defaults = get_settings()
    assert defaults.enable_etsy is True
    assert defaults.etsy_keystring is None
    assert defaults.etsy_shared_secret is None

    monkeypatch.setenv("ETSY_API_KEY", "legacy-fake-key")
    get_settings.cache_clear()
    assert get_settings().etsy_keystring is None

    monkeypatch.setenv("ETSY_KEYSTRING", "etsy-fake-key")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "etsy-fake-secret")
    monkeypatch.setenv("ENABLE_ETSY", "false")
    get_settings.cache_clear()
    configured = get_settings()
    assert configured.etsy_keystring == "etsy-fake-key"
    assert configured.etsy_shared_secret == "etsy-fake-secret"
    assert configured.enable_etsy is False
    get_settings.cache_clear()


def test_etsy_seed_queries_cover_demo_matrix() -> None:
    queries = set(etsy_seed_queries(SEED_DIR))

    assert len(queries) == 50
    assert queries == {
        (keyword, country)
        for keyword in DEMO_COMPETITOR_KEYWORDS
        for country in DEMO_COUNTRIES
    }


@pytest.mark.parametrize(
    ("keystring", "shared_secret"),
    [(None, "fake-secret"), ("fake-key", None)],
)
def test_etsy_search_missing_credentials_uses_csv_fallback(
    keystring: str | None,
    shared_secret: str | None,
) -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"results": []})

    provider = EtsyProvider(
        settings=Settings(etsy_keystring=keystring, etsy_shared_secret=shared_secret, enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_listings("home decor", country="US"))

    assert calls == 0
    assert result.provider == "etsy"
    assert result.keyword == "home decor"
    assert result.country == "US"
    assert result.fallback_used is True
    assert result.items
    assert all(item.platform == "Etsy" for item in result.items)
    assert all(item.source_type == "csv_fallback" for item in result.items)


def test_etsy_search_disabled_uses_csv_fallback_even_with_credentials() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"results": []})

    provider = EtsyProvider(
        settings=Settings(
            etsy_keystring="disabled-fake-key",
            etsy_shared_secret="disabled-fake-secret",
            enable_etsy=False,
        ),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_listings("pet cooling mat", country="GB"))

    assert calls == 0
    assert result.fallback_used is True
    assert result.items[0].source_type == "csv_fallback"
    serialized = result.model_dump_json()
    assert "disabled-fake-key" not in serialized
    assert "disabled-fake-secret" not in serialized


def test_etsy_search_parses_mock_response_and_does_not_leak_credentials() -> None:
    requests: list[httpx.Request] = []
    collected_at = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-api-key"] == "provider-fake-key:provider-fake-secret"
        assert "authorization" not in request.headers
        assert "x-api-key" not in request.url.params
        assert request.url.params["keywords"] == "boho bedroom"
        assert request.url.params["buyer_country"] == "US"
        assert request.url.params["limit"] == "20"
        assert request.url.params["sort_on"] == "score"
        assert request.url.params["sort_order"] == "desc"
        assert request.url.params["is_safe"] == "true"
        assert request.url.params["currency"] == "USD"
        return httpx.Response(
            200,
            json={
                "count": 1,
                "results": [
                    {
                        "listing_id": 123,
                        "title": "Handmade cotton throw blanket",
                        "url": "https://www.etsy.com/listing/123/example",
                        "price": {"amount": 5000, "divisor": 100, "currency_code": "USD"},
                        "converted_price": {"amount": 4600, "divisor": 100, "currency_code": "USD"},
                        "taxonomy_path": ["Home & Living", "Bedding", "Blankets & Throws"],
                        "images": [
                            {"rank": 2, "url_fullxfull": "https://img.example/second.jpg"},
                            {"rank": 1, "url_570xN": "https://img.example/first.jpg"},
                        ],
                        "shop": {
                            "review_average": 4.82,
                            "review_count": 312,
                            "shop_location_country_iso": "US",
                        },
                        "num_favorers": 9999,
                    }
                ],
            },
        )

    provider = EtsyProvider(
        settings=Settings(
            etsy_keystring="provider-fake-key",
            etsy_shared_secret="provider-fake-secret",
            enable_etsy=True,
        ),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
        clock=lambda: collected_at,
    )

    result = asyncio.run(provider.search_listings("Boho Bedroom", country="us", limit=50))

    assert result.fallback_used is False
    assert len(result.items) == 1
    item = result.items[0]
    assert item.platform == "Etsy"
    assert item.country == "US"
    assert item.keyword == "boho bedroom"
    assert item.title == "Handmade cotton throw blanket"
    assert item.price == Decimal("46")
    assert item.currency == "USD"
    assert item.product_url == "https://www.etsy.com/listing/123/example"
    assert item.image_url == "https://img.example/first.jpg"
    assert item.category == "Home & Living > Bedding > Blankets & Throws"
    assert item.rating == Decimal("4.82")
    assert item.review_count == 312
    assert item.source_type == "api"
    assert item.collected_at == collected_at
    serialized = result.model_dump_json()
    assert "provider-fake-key" not in serialized
    assert "provider-fake-secret" not in serialized
    assert "9999" not in serialized
    assert requests


def test_etsy_openapi_ping_validates_configured_credentials() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path.endswith("/openapi-ping")
        assert request.headers["x-api-key"] == "ping-fake-key:ping-fake-secret"
        return httpx.Response(200, json={"ok": True})

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="ping-fake-key", etsy_shared_secret="ping-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    assert asyncio.run(provider.openapi_ping()) is True
    assert len(requests) == 1


def test_etsy_listing_access_error_is_distinguishable_and_fallback_safe() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "access restricted"})

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="access-fake-key", etsy_shared_secret="access-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    with pytest.raises(Exception) as exc_info:
        asyncio.run(provider.search_listings("home decor", country="US", limit=1, allow_fallback=False))

    assert getattr(exc_info.value, "code") == "credentials_valid_but_listing_search_requires_oauth_or_approval"

    fallback = asyncio.run(provider.search_listings("home decor", country="US", limit=1))
    assert fallback.fallback_used is True
    assert fallback.items
    assert fallback.items[0].source_type == "csv_fallback"
    serialized = fallback.model_dump_json()
    assert "access-fake-key" not in serialized
    assert "access-fake-secret" not in serialized


def test_etsy_listing_oauth_body_error_is_distinguishable() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "OAuth approval required for listing access"})

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="body-fake-key", etsy_shared_secret="body-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    with pytest.raises(Exception) as exc_info:
        asyncio.run(provider.search_listings("home decor", country="US", limit=1, allow_fallback=False))

    assert getattr(exc_info.value, "code") == "credentials_valid_but_listing_search_requires_oauth_or_approval"
    assert "body-fake-key" not in str(exc_info.value)
    assert "body-fake-secret" not in str(exc_info.value)


def test_etsy_search_schema_matches_contract() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "listing_id": 789,
                        "title": "Dorm bedding checklist",
                        "price": {"amount": 8400, "divisor": 100, "currency_code": "USD"},
                    }
                ]
            },
        )

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="schema-fake-key", etsy_shared_secret="schema-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_listings("dorm room bedding"))

    assert EtsySearchResponse.model_validate(result.model_dump()) == result
    assert result.items[0].product_url == "https://www.etsy.com/listing/789"
    assert result.items[0].category is None


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_etsy_search_falls_back_on_api_error(status_code: int) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "upstream failure"})

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="error-fake-key", etsy_shared_secret="error-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_listings("cotton bedding set", country="US"))

    assert result.fallback_used is True
    assert result.items
    assert all(item.source_type == "csv_fallback" for item in result.items)
    serialized = result.model_dump_json()
    assert "error-fake-key" not in serialized
    assert "error-fake-secret" not in serialized


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"results": []}),
        httpx.Response(200, json={"items": []}),
    ],
)
def test_etsy_search_falls_back_on_invalid_or_empty_response(response: httpx.Response) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return response

    provider = EtsyProvider(
        settings=Settings(etsy_keystring="invalid-fake-key", etsy_shared_secret="invalid-fake-secret", enable_etsy=True),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.search_listings("baby swaddle", country="GB"))

    assert result.fallback_used is True
    assert result.items


def test_etsy_search_rejects_unsupported_inputs() -> None:
    provider = EtsyProvider(settings=Settings(etsy_keystring=None, etsy_shared_secret=None), seed_dir=SEED_DIR)

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.search_listings("   "))

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.search_listings("home decor", country="USA"))


def _clear_etsy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ETSY_KEYSTRING",
        "ETSY_API_KEY",
        "ETSY_SHARED_SECRET",
        "ENABLE_ETSY",
        "SUPIN_ETSY_KEYSTRING",
        "SUPIN_ETSY_SHARED_SECRET",
        "SUPIN_ENABLE_ETSY",
    ):
        monkeypatch.delenv(name, raising=False)
