import asyncio
from pathlib import Path

import httpx
import pytest

from app.schemas import WorldBankCountryResponse
from app.services.providers import DataProviderValidationError
from app.services.providers.worldbank import WorldBankProvider


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"


def test_worldbank_fetch_country_no_key_and_normalizes_latest_indicators() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "api_key" not in request.url.params
        assert "key" not in request.url.params
        return httpx.Response(
            200,
            json=[
                {"page": 1, "pages": 1},
                [
                    _row("SP.POP.TOTL", "Population, total", "2025", None),
                    _row("SP.POP.TOTL", "Population, total", "2024", 340110988),
                    _row("NY.GDP.MKTP.CD", "GDP (current US$)", "2024", 29184890000000),
                    _row("NY.GDP.PCAP.CD", "GDP per capita (current US$)", "2024", 82769.4),
                    _row("IT.NET.USER.ZS", "Individuals using the Internet", "2023", 92.0),
                    _row("SP.URB.TOTL.IN.ZS", "Urban population", "2024", 83.3),
                ],
            ],
        )

    provider = WorldBankProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.fetch_country("us"))

    assert result.provider == "worldbank"
    assert result.country_code == "US"
    assert result.fallback_used is False
    assert {item.indicator_code for item in result.indicators} == {
        "NY.GDP.MKTP.CD",
        "NY.GDP.PCAP.CD",
        "SP.POP.TOTL",
        "IT.NET.USER.ZS",
        "SP.URB.TOTL.IN.ZS",
    }
    population = next(item for item in result.indicators if item.indicator_code == "SP.POP.TOTL")
    assert population.year == 2024
    assert population.value == 340110988
    assert all(item.source == "api" for item in result.indicators)
    assert requests


def test_worldbank_fetch_country_schema_matches_contract() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"page": 1},
                [_row("NY.GDP.PCAP.CD", "GDP per capita (current US$)", "2024", 82769.4)],
            ],
        )

    provider = WorldBankProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.fetch_country("US"))

    assert WorldBankCountryResponse.model_validate(result.model_dump()) == result


def test_worldbank_fetch_country_falls_back_to_market_profiles_on_api_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "temporary"})

    provider = WorldBankProvider(transport=httpx.MockTransport(handler), seed_dir=SEED_DIR)

    result = asyncio.run(provider.fetch_country("US"))

    assert result.fallback_used is True
    assert result.country_code == "US"
    assert all(item.source == "csv_fallback" for item in result.indicators)
    codes = {item.indicator_code for item in result.indicators}
    assert {"NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "SP.POP.TOTL", "IT.NET.USER.ZS"} <= codes
    assert "SP.URB.TOTL.IN.ZS" not in codes
    gdp = next(item for item in result.indicators if item.indicator_code == "NY.GDP.MKTP.CD")
    assert gdp.value and gdp.value > 1_000_000_000_000


def test_worldbank_fetch_country_rejects_unsupported_country() -> None:
    provider = WorldBankProvider(seed_dir=SEED_DIR)

    with pytest.raises(DataProviderValidationError):
        asyncio.run(provider.fetch_country("ZZ"))


def _row(indicator_code: str, indicator_name: str, year: str, value: float | int | None) -> dict[str, object]:
    return {
        "indicator": {"id": indicator_code, "value": indicator_name},
        "country": {"id": "US", "value": "United States"},
        "date": year,
        "value": value,
    }
