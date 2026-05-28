from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.schemas import (
    EtsyListingItem,
    EtsySearchResponse,
    GdeltArticleItem,
    GdeltSearchResponse,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
    YoutubeSearchResponse,
    YoutubeVideoItem,
)
from app.services.ai import BailianAuthenticationError, BailianChatCompletion
from app.services.provider_status import ProviderStatusService, get_provider_status_service


EXPECTED_PROVIDERS = {
    "bailian",
    "worldbank",
    "gdelt",
    "youtube",
    "etsy",
    "un_comtrade",
    "csv_fallback",
    "ebay",
    "rakuten",
    "reddit",
}
SECRET_MARKERS = (
    "dashscope-fake-value",
    "youtube-fake-value",
    "etsy-fake-value",
    "etsy-fake-shared-value",
    "un-fake-value",
    "ebay-fake-value",
    "ebay-fake-shared-value",
    "rakuten-fake-value",
    "reddit-fake-value",
    "reddit-fake-shared-value",
    "authorization",
    "x-api-key",
    "subscription-key",
)


def test_provider_status_endpoint_returns_expected_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert set(providers) == EXPECTED_PROVIDERS
    assert providers["bailian"]["status"] == "not_configured"
    assert providers["worldbank"]["status"] == "active_no_key"
    assert providers["gdelt"]["status"] == "active_no_key"
    assert providers["youtube"]["status"] == "not_configured"
    assert providers["etsy"]["status"] == "not_configured"
    assert providers["un_comtrade"]["status"] == "optional_no_key_first"
    assert providers["csv_fallback"]["status"] == "active_no_key"
    assert providers["ebay"]["status"] == "pending_manual_registration"
    assert providers["rakuten"]["status"] == "pending_manual_registration"
    assert providers["reddit"]["status"] == "pending_manual_registration"
    get_settings.cache_clear()


def test_provider_status_endpoint_uses_safe_configured_states(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-fake-value")
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "youtube-fake-value")
    monkeypatch.setenv("ETSY_KEYSTRING", "etsy-fake-value")
    monkeypatch.setenv("UN_COMTRADE_API_KEY", "un-fake-value")
    monkeypatch.setenv("EBAY_CLIENT_ID", "ebay-fake-value")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "ebay-fake-shared-value")
    monkeypatch.setenv("RAKUTEN_APP_ID", "rakuten-fake-value")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "reddit-fake-value")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "reddit-fake-shared-value")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert providers["bailian"]["status"] == "configured"
    assert providers["youtube"]["status"] == "configured"
    assert providers["etsy"]["status"] == "configured"
    assert providers["ebay"]["status"] == "pending_manual_registration"
    assert providers["rakuten"]["status"] == "pending_manual_registration"
    assert providers["reddit"]["status"] == "pending_manual_registration"
    _assert_no_secret_markers(response.text)
    get_settings.cache_clear()


def test_provider_status_endpoint_respects_disabled_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "youtube-fake-value")
    monkeypatch.setenv("ENABLE_YOUTUBE", "false")
    monkeypatch.setenv("ETSY_KEYSTRING", "etsy-fake-value")
    monkeypatch.setenv("ENABLE_ETSY", "false")
    monkeypatch.setenv("ENABLE_UN_COMTRADE", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/api/admin/providers/status")

    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert providers["youtube"]["status"] == "disabled"
    assert providers["youtube"]["default_enabled"] is False
    assert providers["etsy"]["status"] == "disabled"
    assert providers["un_comtrade"]["status"] == "disabled"
    _assert_no_secret_markers(response.text)
    get_settings.cache_clear()


def test_bailian_test_maps_missing_success_and_failure() -> None:
    with _override_provider_service(ProviderStatusService(settings=Settings(bailian_api_key=None))):
        with TestClient(app) as client:
            missing_response = client.post("/api/admin/providers/test/bailian")

    assert missing_response.status_code == 200
    assert missing_response.json()["status"] == "pending"

    success_service = ProviderStatusService(
        settings=Settings(bailian_api_key="dashscope-fake-value"),
        bailian_client=StubBailianClient(),
    )
    with _override_provider_service(success_service):
        with TestClient(app) as client:
            success_response = client.post("/api/admin/providers/test/bailian")

    assert success_response.status_code == 200
    assert success_response.json()["status"] == "success"
    assert success_response.json()["sample_count"] == 1

    failure_service = ProviderStatusService(
        settings=Settings(bailian_api_key="dashscope-fake-value"),
        bailian_client=StubBailianClient(fail=True),
    )
    with _override_provider_service(failure_service):
        with TestClient(app) as client:
            failure_response = client.post("/api/admin/providers/test/bailian")

    assert failure_response.status_code == 200
    assert failure_response.json()["status"] == "unavailable"
    assert failure_response.json()["error_code"] == "BAILIAN_AUTHENTICATION_ERROR"
    for response in (missing_response, success_response, failure_response):
        _assert_no_secret_markers(response.text)


def test_provider_test_endpoint_maps_live_and_fallback_payloads() -> None:
    service = ProviderStatusService(
        settings=Settings(),
        worldbank_provider=StubWorldBankProvider(),
        gdelt_provider=StubGdeltProvider(fallback=True),
        youtube_provider=StubYoutubeProvider(),
        etsy_provider=StubEtsyProvider(fallback=True),
        un_comtrade_provider=StubUnComtradeProvider(fallback=True),
    )

    with _override_provider_service(service):
        with TestClient(app) as client:
            worldbank_response = client.post("/api/admin/providers/test/worldbank")
            gdelt_response = client.post("/api/admin/providers/test/gdelt")
            youtube_response = client.post("/api/admin/providers/test/youtube")
            etsy_response = client.post("/api/admin/providers/test/etsy")
            un_response = client.post("/api/admin/providers/test/un_comtrade")

    assert worldbank_response.json()["status"] == "success"
    assert gdelt_response.json()["status"] == "fallback"
    assert youtube_response.json()["status"] == "success"
    assert etsy_response.json()["status"] == "fallback"
    assert un_response.json()["status"] == "fallback"
    assert service._gdelt_provider.calls == [("home textile", None, 1)]  # type: ignore[attr-defined]
    for response in (worldbank_response, gdelt_response, youtube_response, etsy_response, un_response):
        assert response.status_code == 200
        assert response.json()["sample_count"] > 0
        _assert_no_secret_markers(response.text)


def test_provider_test_endpoint_handles_empty_payload_as_unavailable() -> None:
    service = ProviderStatusService(settings=Settings(), worldbank_provider=StubWorldBankProvider(empty=True))

    with _override_provider_service(service):
        with TestClient(app) as client:
            response = client.post("/api/admin/providers/test/worldbank")

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["error_code"] == "EMPTY_PROVIDER_RESPONSE"


def test_csv_fallback_test_validates_seed_files(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    for filename in (
        "competitor_samples.csv",
        "content_trends.csv",
        "market_profiles.csv",
        "product_catalog.csv",
        "trade_samples.csv",
        "user_discussions.csv",
    ):
        (seed_dir / filename).write_text("name,value\nsample,1\n", encoding="utf-8")

    service = ProviderStatusService(settings=Settings(), seed_dir=seed_dir)
    with _override_provider_service(service):
        with TestClient(app) as client:
            success_response = client.post("/api/admin/providers/test/csv_fallback")

    assert success_response.status_code == 200
    assert success_response.json()["status"] == "success"
    assert success_response.json()["sample_count"] == 6

    (seed_dir / "content_trends.csv").write_text("name,value\n", encoding="utf-8")
    with _override_provider_service(service):
        with TestClient(app) as client:
            unavailable_response = client.post("/api/admin/providers/test/csv_fallback")

    assert unavailable_response.status_code == 200
    assert unavailable_response.json()["status"] == "unavailable"


def test_future_providers_return_pending_even_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EBAY_CLIENT_ID", "ebay-fake-value")
    monkeypatch.setenv("RAKUTEN_APP_ID", "rakuten-fake-value")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "reddit-fake-value")
    get_settings.cache_clear()
    with TestClient(app) as client:
        responses = [
            client.post("/api/admin/providers/test/ebay"),
            client.post("/api/admin/providers/test/rakuten"),
            client.post("/api/admin/providers/test/reddit"),
        ]

    for response in responses:
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        _assert_no_secret_markers(response.text)
    get_settings.cache_clear()


def test_unknown_provider_returns_validation_error() -> None:
    with TestClient(app) as client:
        response = client.post("/api/admin/providers/test/unknown")

    assert response.status_code == 422
    _assert_no_secret_markers(response.text)


class StubBailianClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        if self.fail:
            raise BailianAuthenticationError("do not expose this")
        return BailianChatCompletion(content="OK", model="qwen3.6-plus")


class StubWorldBankProvider:
    def __init__(self, *, fallback: bool = False, empty: bool = False) -> None:
        self.fallback = fallback
        self.empty = empty

    async def fetch_country(self, country_code: str) -> WorldBankCountryResponse:
        return WorldBankCountryResponse(
            country_code=country_code.upper(),
            indicators=[]
            if self.empty
            else [
                WorldBankIndicatorItem(
                    indicator_code="SP.POP.TOTL",
                    indicator_name="Population",
                    year=2024,
                    value=1.0,
                    source="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubGdeltProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls: list[tuple[str, str | None, int]] = []

    async def search(
        self,
        query: str,
        *,
        country: str | None = None,
        max_records: int = 10,
    ) -> GdeltSearchResponse:
        self.calls.append((query, country, max_records))
        return GdeltSearchResponse(
            query=query,
            items=[
                GdeltArticleItem(
                    title="sample",
                    url="https://example.test/news",
                    source="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubYoutubeProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback

    async def search_videos(
        self,
        keyword: str,
        country: str = "US",
        max_results: int = 10,
    ) -> YoutubeSearchResponse:
        return YoutubeSearchResponse(
            keyword=keyword,
            country=country,
            items=[
                YoutubeVideoItem(
                    country=country,
                    keyword=keyword,
                    title="sample video",
                    source_type="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
        )


class StubEtsyProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback

    async def search_listings(
        self,
        keyword: str,
        country: str = "US",
        limit: int = 20,
    ) -> EtsySearchResponse:
        return EtsySearchResponse(
            keyword=keyword,
            country=country,
            items=[
                EtsyListingItem(
                    country=country,
                    keyword=keyword,
                    title="sample listing",
                    price=Decimal("10"),
                    currency="USD",
                    source_type="csv_fallback" if self.fallback else "api",
                    collected_at=datetime(2026, 5, 28, tzinfo=timezone.utc),
                )
            ],
            fallback_used=self.fallback,
        )


class StubUnComtradeProvider:
    def __init__(self, *, fallback: bool = False) -> None:
        self.fallback = fallback

    async def get_trade_flow(
        self,
        reporter: str = "CHN",
        partner: str = "USA",
        hs_code: str = "6302",
        flow: str = "export",
        start_year: int = 2024,
        end_year: int = 2024,
    ) -> UnComtradeTradeFlowResponse:
        return UnComtradeTradeFlowResponse(
            hs_code=hs_code,
            reporter=reporter,
            partner=partner,
            flow="export",
            records=[
                UnComtradeTradeRecord(
                    year=start_year,
                    trade_value_usd=Decimal("100"),
                    quantity=Decimal("1"),
                    source="csv_fallback" if self.fallback else "api",
                )
            ],
            fallback_used=self.fallback,
            auth_mode="fallback" if self.fallback else "no_key",
        )


class _override_provider_service:
    def __init__(self, service: ProviderStatusService) -> None:
        self.service = service

    def __enter__(self) -> None:
        app.dependency_overrides[get_provider_status_service] = lambda: self.service

    def __exit__(self, *args: object) -> None:
        app.dependency_overrides.pop(get_provider_status_service, None)


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DASHSCOPE_API_KEY",
        "BAILIAN_API_KEY",
        "YOUTUBE_DATA_API_KEY",
        "ENABLE_YOUTUBE",
        "ETSY_KEYSTRING",
        "ETSY_SHARED_SECRET",
        "ENABLE_ETSY",
        "UN_COMTRADE_API_KEY",
        "ENABLE_UN_COMTRADE",
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET",
        "RAKUTEN_APP_ID",
        "RAKUTEN_APPLICATION_ID",
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


def _assert_no_secret_markers(text: str) -> None:
    lowered = text.lower()
    for marker in SECRET_MARKERS:
        assert marker not in lowered
