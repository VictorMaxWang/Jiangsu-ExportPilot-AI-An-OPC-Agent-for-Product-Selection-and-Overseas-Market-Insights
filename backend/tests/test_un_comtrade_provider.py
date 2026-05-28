import asyncio
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.schemas import UnComtradeTradeFlowResponse
from app.services.providers import DataProviderValidationError
from app.services.providers.un_comtrade import UnComtradeProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"


def test_un_comtrade_settings_defaults_key_and_enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_un_comtrade_env(monkeypatch)
    get_settings.cache_clear()
    defaults = get_settings()
    assert defaults.enable_un_comtrade is True
    assert defaults.un_comtrade_api_key is None

    monkeypatch.setenv("UN_COMTRADE_API_KEY", "un-comtrade-fake-key")
    monkeypatch.setenv("ENABLE_UN_COMTRADE", "false")
    get_settings.cache_clear()
    configured = get_settings()
    assert configured.un_comtrade_api_key == "un-comtrade-fake-key"
    assert configured.enable_un_comtrade is False
    get_settings.cache_clear()


def test_un_comtrade_trade_flow_no_key_first_and_normalizes_rows() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "key" not in request.url.params
        assert "api_key" not in request.url.params
        assert "subscription-key" not in request.url.params
        assert request.url.params["reporterCode"] == "156"
        assert request.url.params["partnerCode"] == "842"
        assert request.url.params["cmdCode"] == "6302"
        assert request.url.params["flowCode"] == "X"
        assert request.url.params["period"] == "2024"
        return httpx.Response(
            200,
            json={
                "elapsedTime": "0.01 secs",
                "count": 1,
                "data": [
                    {
                        "period": "2024",
                        "primaryValue": 2973428229,
                        "qty": 435634831.573,
                    }
                ],
                "error": "",
            },
        )

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key=None),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(
        provider.get_trade_flow(
            reporter="China",
            partner="US",
            hs_code="6302",
            flow="exports",
            start_year=2024,
            end_year=2024,
        )
    )

    assert result.provider == "un_comtrade"
    assert result.reporter == "CHN"
    assert result.partner == "USA"
    assert result.flow == "export"
    assert result.fallback_used is False
    assert result.auth_mode == "no_key"
    assert len(result.records) == 1
    assert result.records[0].year == 2024
    assert result.records[0].trade_value_usd == Decimal("2973428229")
    assert result.records[0].quantity == Decimal("435634831.573")
    assert result.records[0].source == "api"
    assert len(requests) == 1


@pytest.mark.parametrize("status_code", [401, 403, 429])
def test_un_comtrade_trade_flow_retries_with_optional_key(status_code: int) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            assert request.url.path.endswith("/preview")
            assert "subscription-key" not in request.url.params
            return httpx.Response(status_code, json={"error": "subscription key required", "data": []})

        assert request.url.path.endswith("/keyed")
        assert request.url.params["subscription-key"] == "provider-fake-un-key"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "refYear": 2024,
                        "primaryValue": "123456",
                        "qty": "123",
                    }
                ],
                "error": "",
            },
        )

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key="provider-fake-un-key"),
        no_key_endpoint="https://comtrade.example/preview",
        key_endpoint="https://comtrade.example/keyed",
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(start_year=2024, end_year=2024))

    assert result.fallback_used is False
    assert result.auth_mode == "key"
    assert result.records[0].source == "api"
    assert "provider-fake-un-key" not in result.model_dump_json()
    assert len(requests) == 2


def test_un_comtrade_trade_flow_retries_on_subscription_error_payload() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"data": [], "error": "missing subscription-key"})
        return httpx.Response(200, json={"data": [{"period": "2024", "primaryValue": 77, "qty": 7}], "error": ""})

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key="payload-fake-key"),
        no_key_endpoint="https://comtrade.example/preview",
        key_endpoint="https://comtrade.example/keyed",
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(start_year=2024, end_year=2024))

    assert result.auth_mode == "key"
    assert result.records[0].trade_value_usd == Decimal("77")
    assert "payload-fake-key" not in result.model_dump_json()


@pytest.mark.parametrize("status_code", [401, 403, 429, 500])
def test_un_comtrade_trade_flow_falls_back_without_key(status_code: int) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "upstream failure", "data": []})

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key=None),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(hs_code="6302", start_year=2023, end_year=2024))

    assert result.fallback_used is True
    assert result.auth_mode == "fallback"
    assert result.reporter == "CHN"
    assert result.partner == "USA"
    assert result.records
    assert all(record.source == "csv_fallback" for record in result.records)
    values = {record.year: record.trade_value_usd for record in result.records}
    assert values[2023] == Decimal("1783000000")
    assert values[2024] == Decimal("1863000000")


def test_un_comtrade_trade_flow_disabled_uses_csv_fallback_without_request() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": [{"period": "2024", "primaryValue": 1}]})

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=False, un_comtrade_api_key="disabled-fake-key"),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(hs_code="630221", start_year=2024, end_year=2024))

    assert calls == 0
    assert result.fallback_used is True
    assert result.auth_mode == "fallback"
    assert result.records[0].trade_value_usd == Decimal("1342000000")
    assert "disabled-fake-key" not in result.model_dump_json()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"data": []}),
        httpx.Response(200, json={"items": []}),
    ],
)
def test_un_comtrade_trade_flow_falls_back_on_invalid_or_empty_response(response: httpx.Response) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return response

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key="invalid-fake-key"),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(hs_code="630140", start_year=2024, end_year=2024))

    assert result.fallback_used is True
    assert result.auth_mode == "fallback"
    assert result.records
    assert "invalid-fake-key" not in result.model_dump_json()


def test_un_comtrade_trade_flow_schema_matches_contract() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"period": "2024", "primaryValue": 88, "qty": 8}], "error": ""})

    provider = UnComtradeProvider(
        settings=Settings(enable_un_comtrade=True, un_comtrade_api_key=None),
        transport=httpx.MockTransport(handler),
        seed_dir=SEED_DIR,
    )

    result = asyncio.run(provider.get_trade_flow(start_year=2024, end_year=2024))

    assert UnComtradeTradeFlowResponse.model_validate(result.model_dump()) == result


def test_un_comtrade_trade_flow_rejects_unsupported_inputs() -> None:
    provider = UnComtradeProvider(settings=Settings(enable_un_comtrade=False), seed_dir=SEED_DIR)

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.get_trade_flow(reporter="ZZZ"))

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.get_trade_flow(flow="sideways"))

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.get_trade_flow(hs_code="63AA"))

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.get_trade_flow(start_year=2025, end_year=2024))


def _clear_un_comtrade_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "UN_COMTRADE_API_KEY",
        "SUPIN_UN_COMTRADE_API_KEY",
        "ENABLE_UN_COMTRADE",
        "SUPIN_ENABLE_UN_COMTRADE",
    ):
        monkeypatch.delenv(name, raising=False)
