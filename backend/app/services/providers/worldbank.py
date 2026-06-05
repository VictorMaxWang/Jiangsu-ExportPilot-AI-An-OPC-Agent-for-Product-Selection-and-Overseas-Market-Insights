from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.core.countries import COUNTRY_NAMES_EN, TARGET_COUNTRY_CODES, normalize_country_code
from app.schemas import WorldBankCountryResponse, WorldBankIndicatorItem
from app.services.analysis_performance import is_timeout_error, record_provider_http_call
from app.services.providers import (
    API_SOURCE,
    CSV_FALLBACK_SOURCE,
    DEFAULT_PROVIDER_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    DataProviderValidationError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEFAULT_BASE_URL = "https://api.worldbank.org/v2"
FALLBACK_YEAR = 2025

SUPPORTED_COUNTRIES: dict[str, str] = {
    code: COUNTRY_NAMES_EN[code]
    for code in (*TARGET_COUNTRY_CODES, "CN")
}

SUPPORTED_INDICATORS: dict[str, str] = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "SP.POP.TOTL": "Population, total",
    "IT.NET.USER.ZS": "Individuals using the Internet (% of population)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total population)",
}


class _WorldBankApiError(Exception):
    pass


class WorldBankProvider:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def fetch_country(self, country_code: str) -> WorldBankCountryResponse:
        normalized_country = _normalize_country(country_code)
        try:
            indicators = await self._fetch_api_indicators(normalized_country)
            return WorldBankCountryResponse(
                country_code=normalized_country,
                indicators=indicators,
                fallback_used=False,
            )
        except _WorldBankApiError:
            return self._fallback_country(normalized_country)

    async def _fetch_api_indicators(self, country_code: str) -> list[WorldBankIndicatorItem]:
        indicator_codes = ";".join(SUPPORTED_INDICATORS)
        current_year = datetime.now(timezone.utc).year
        params = {
            "format": "json",
            "source": "2",
            "date": f"{current_year - 8}:{current_year}",
            "per_page": "100",
        }
        timeout = httpx.Timeout(self._timeout_seconds, connect=DEFAULT_PROVIDER_CONNECT_TIMEOUT_SECONDS)
        url = f"{self._base_url}/country/{country_code}/indicator/{indicator_codes}"

        started_at = datetime.now(timezone.utc)
        start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            timeout_error = is_timeout_error(exc)
            record_provider_http_call(
                provider="worldbank",
                endpoint="market_profile_http",
                status="timeout" if timeout_error else "error",
                started_at=started_at,
                duration_ms=max(0, round((perf_counter() - start) * 1000)),
                timeout=timeout_error,
                country=country_code,
            )
            raise _WorldBankApiError("World Bank request failed") from exc

        record_provider_http_call(
            provider="worldbank",
            endpoint="market_profile_http",
            status="success" if response.status_code < 400 else "error",
            started_at=started_at,
            duration_ms=max(0, round((perf_counter() - start) * 1000)),
            country=country_code,
            http_status=response.status_code,
        )
        if response.status_code >= 400:
            raise _WorldBankApiError("World Bank returned an error status")

        try:
            payload = response.json()
        except ValueError as exc:
            raise _WorldBankApiError("World Bank returned invalid JSON") from exc

        rows = _extract_worldbank_rows(payload)
        indicators = _latest_indicators(rows)
        if not indicators:
            raise _WorldBankApiError("World Bank returned no usable indicators")
        return indicators

    def _fallback_country(self, country_code: str) -> WorldBankCountryResponse:
        row = _find_market_profile(country_code, self._seed_dir)
        if row is None:
            return WorldBankCountryResponse(
                country_code=country_code,
                indicators=[],
                fallback_used=True,
            )

        gdp_per_capita = _optional_decimal(row.get("gdp_per_capita"))
        population = _optional_decimal(row.get("population"))
        internet_penetration = _optional_decimal(row.get("internet_penetration"))

        indicators: list[WorldBankIndicatorItem] = []
        if gdp_per_capita is not None and population is not None:
            indicators.append(
                _fallback_indicator(
                    "NY.GDP.MKTP.CD",
                    gdp_per_capita * population,
                )
            )
        if gdp_per_capita is not None:
            indicators.append(_fallback_indicator("NY.GDP.PCAP.CD", gdp_per_capita))
        if population is not None:
            indicators.append(_fallback_indicator("SP.POP.TOTL", population))
        if internet_penetration is not None:
            indicators.append(_fallback_indicator("IT.NET.USER.ZS", internet_penetration))

        return WorldBankCountryResponse(
            country_code=country_code,
            indicators=indicators,
            fallback_used=True,
        )


def _normalize_country(country_code: str) -> str:
    normalized = normalize_country_code(country_code)
    if normalized not in SUPPORTED_COUNTRIES:
        supported = ", ".join(SUPPORTED_COUNTRIES)
        raise DataProviderValidationError(f"Unsupported World Bank country_code: {country_code}. Supported: {supported}")
    return normalized


def _extract_worldbank_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise _WorldBankApiError("World Bank response did not match expected list format")
    return [row for row in payload[1] if isinstance(row, dict)]


def _latest_indicators(rows: list[dict[str, Any]]) -> list[WorldBankIndicatorItem]:
    latest: dict[str, tuple[int, float]] = {}
    for row in rows:
        indicator = row.get("indicator")
        if not isinstance(indicator, dict):
            continue
        indicator_code = str(indicator.get("id") or "")
        if indicator_code not in SUPPORTED_INDICATORS or row.get("value") is None:
            continue
        try:
            year = int(str(row.get("date")))
            value = float(row["value"])
        except (TypeError, ValueError):
            continue
        if indicator_code not in latest or year > latest[indicator_code][0]:
            latest[indicator_code] = (year, value)

    return [
        WorldBankIndicatorItem(
            indicator_code=indicator_code,
            indicator_name=SUPPORTED_INDICATORS[indicator_code],
            year=year_value[0],
            value=year_value[1],
            source=API_SOURCE,
        )
        for indicator_code, year_value in latest.items()
    ]


def _find_market_profile(country_code: str, seed_dir: Path) -> dict[str, str] | None:
    path = (seed_dir / "market_profiles.csv").resolve()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            for row in csv.DictReader(csv_file):
                cleaned = _clean_row(row)
                if cleaned.get("country_code", "").upper() == country_code:
                    return cleaned
    except (OSError, csv.Error):
        return None
    return None


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def _fallback_indicator(indicator_code: str, value: Decimal) -> WorldBankIndicatorItem:
    return WorldBankIndicatorItem(
        indicator_code=indicator_code,
        indicator_name=SUPPORTED_INDICATORS[indicator_code],
        year=FALLBACK_YEAR,
        value=float(value),
        source=CSV_FALLBACK_SOURCE,
    )
