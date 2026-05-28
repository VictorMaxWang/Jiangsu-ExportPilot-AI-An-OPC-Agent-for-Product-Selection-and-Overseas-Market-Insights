from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import httpx

from app.core.config import Settings, get_settings
from app.schemas import UnComtradeTradeFlowResponse, UnComtradeTradeRecord
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE, DataProviderValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEFAULT_NO_KEY_ENDPOINT = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
DEFAULT_KEY_ENDPOINT = "https://comtradeapi.un.org/data/v1/get/C/A/HS"
MAX_RECORDS = 500


@dataclass(frozen=True)
class _Country:
    iso3: str
    comtrade_code: str


@dataclass(frozen=True)
class UnComtradeSeedQuery:
    reporter: str
    partner: str
    hs_code: str
    flow: Literal["export", "import"]
    start_year: int
    end_year: int


_COUNTRY_ALIASES: dict[str, _Country] = {
    "CHN": _Country("CHN", "156"),
    "CN": _Country("CHN", "156"),
    "CHINA": _Country("CHN", "156"),
    "PEOPLES REPUBLIC OF CHINA": _Country("CHN", "156"),
    "USA": _Country("USA", "842"),
    "US": _Country("USA", "842"),
    "UNITED STATES": _Country("USA", "842"),
    "UNITED STATES OF AMERICA": _Country("USA", "842"),
    "GBR": _Country("GBR", "826"),
    "GB": _Country("GBR", "826"),
    "UK": _Country("GBR", "826"),
    "UNITED KINGDOM": _Country("GBR", "826"),
    "JPN": _Country("JPN", "392"),
    "JP": _Country("JPN", "392"),
    "JAPAN": _Country("JPN", "392"),
    "AUS": _Country("AUS", "36"),
    "AU": _Country("AUS", "36"),
    "AUSTRALIA": _Country("AUS", "36"),
    "SGP": _Country("SGP", "702"),
    "SG": _Country("SGP", "702"),
    "SINGAPORE": _Country("SGP", "702"),
}

_FLOW_ALIASES: dict[str, Literal["export", "import"]] = {
    "X": "export",
    "EXPORT": "export",
    "EXPORTS": "export",
    "M": "import",
    "IMPORT": "import",
    "IMPORTS": "import",
}


class _UnComtradeApiError(Exception):
    def __init__(self, message: str, *, retry_with_key: bool = False) -> None:
        self.retry_with_key = retry_with_key
        super().__init__(message)


class UnComtradeProvider:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        no_key_endpoint: str = DEFAULT_NO_KEY_ENDPOINT,
        key_endpoint: str = DEFAULT_KEY_ENDPOINT,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._no_key_endpoint = no_key_endpoint
        self._key_endpoint = key_endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def get_trade_flow(
        self,
        reporter: str = "CHN",
        partner: str = "USA",
        hs_code: str = "6302",
        flow: str = "export",
        start_year: int = 2020,
        end_year: int = 2025,
    ) -> UnComtradeTradeFlowResponse:
        normalized_reporter = _normalize_country(reporter)
        normalized_partner = _normalize_country(partner)
        normalized_hs_code = _normalize_hs_code(hs_code)
        normalized_flow = _normalize_flow(flow)
        _validate_year_range(start_year, end_year)

        if not self._settings.enable_un_comtrade:
            return self._fallback_trade_flow(
                normalized_reporter,
                normalized_partner,
                normalized_hs_code,
                normalized_flow,
                start_year,
                end_year,
            )

        try:
            records = await self._fetch_api_records(
                self._no_key_endpoint,
                normalized_reporter,
                normalized_partner,
                normalized_hs_code,
                normalized_flow,
                start_year,
                end_year,
                auth_mode="no_key",
                subscription_key=None,
            )
            return _response(
                normalized_reporter,
                normalized_partner,
                normalized_hs_code,
                normalized_flow,
                records,
                fallback_used=False,
                auth_mode="no_key",
            )
        except _UnComtradeApiError as exc:
            if exc.retry_with_key and self._settings.un_comtrade_api_key:
                try:
                    records = await self._fetch_api_records(
                        self._key_endpoint,
                        normalized_reporter,
                        normalized_partner,
                        normalized_hs_code,
                        normalized_flow,
                        start_year,
                        end_year,
                        auth_mode="key",
                        subscription_key=self._settings.un_comtrade_api_key,
                    )
                    return _response(
                        normalized_reporter,
                        normalized_partner,
                        normalized_hs_code,
                        normalized_flow,
                        records,
                        fallback_used=False,
                        auth_mode="key",
                    )
                except _UnComtradeApiError:
                    pass

        return self._fallback_trade_flow(
            normalized_reporter,
            normalized_partner,
            normalized_hs_code,
            normalized_flow,
            start_year,
            end_year,
        )

    async def _fetch_api_records(
        self,
        endpoint: str,
        reporter: _Country,
        partner: _Country,
        hs_code: str,
        flow: Literal["export", "import"],
        start_year: int,
        end_year: int,
        *,
        auth_mode: Literal["no_key", "key"],
        subscription_key: str | None,
    ) -> list[UnComtradeTradeRecord]:
        records: list[UnComtradeTradeRecord] = []
        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            for year in range(start_year, end_year + 1):
                params = _api_params(reporter, partner, hs_code, flow, year)
                if subscription_key:
                    params["subscription-key"] = subscription_key
                try:
                    response = await client.get(endpoint, params=params)
                except httpx.HTTPError as exc:
                    raise _UnComtradeApiError("UN Comtrade request failed") from exc

                payload = _response_payload(response)
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise _UnComtradeApiError("UN Comtrade response did not include data")

                for row in rows:
                    if isinstance(row, dict):
                        record = _api_record_from_row(row, default_year=year)
                        if record is not None:
                            records.append(record)

        collapsed = _collapse_records(records, source=API_SOURCE)
        if not collapsed:
            raise _UnComtradeApiError(f"UN Comtrade returned no usable {auth_mode} rows")
        return collapsed

    def _fallback_trade_flow(
        self,
        reporter: _Country,
        partner: _Country,
        hs_code: str,
        flow: Literal["export", "import"],
        start_year: int,
        end_year: int,
    ) -> UnComtradeTradeFlowResponse:
        rows = _read_trade_rows(self._seed_dir)
        matched_rows = [
            row
            for row in rows
            if _row_matches(row, reporter, partner, hs_code, flow, start_year, end_year)
        ]
        if not matched_rows:
            mirror_flow = _opposite_flow(flow)
            matched_rows = [
                row
                for row in rows
                if _row_matches(row, partner, reporter, hs_code, mirror_flow, start_year, end_year)
            ]

        records = _fallback_records_from_rows(matched_rows)
        return _response(
            reporter,
            partner,
            hs_code,
            flow,
            records,
            fallback_used=True,
            auth_mode="fallback",
        )


def un_comtrade_seed_queries(seed_dir: Path | None = None) -> list[UnComtradeSeedQuery]:
    grouped: dict[tuple[str, str, str], tuple[int, int]] = {}
    for row in _read_trade_rows(seed_dir or DEFAULT_SEED_DIR):
        try:
            csv_reporter = _normalize_country(row.get("reporter", ""))
            csv_partner = _normalize_country(row.get("partner", ""))
            csv_flow = _normalize_flow(row.get("flow", ""))
            hs_code = _normalize_hs_code(row.get("hs_code", ""))
            year = int(row.get("year", ""))
        except (DataProviderValidationError, ValueError):
            continue
        if csv_partner.iso3 != "CHN" or csv_flow != "import":
            continue
        key = ("CHN", csv_reporter.iso3, hs_code)
        if key in grouped:
            start_year, end_year = grouped[key]
            grouped[key] = (min(start_year, year), max(end_year, year))
        else:
            grouped[key] = (year, year)

    return [
        UnComtradeSeedQuery(
            reporter=reporter,
            partner=partner,
            hs_code=hs_code,
            flow="export",
            start_year=year_range[0],
            end_year=year_range[1],
        )
        for (reporter, partner, hs_code), year_range in sorted(grouped.items())
    ]


def _api_params(
    reporter: _Country,
    partner: _Country,
    hs_code: str,
    flow: Literal["export", "import"],
    year: int,
) -> dict[str, str]:
    return {
        "reporterCode": reporter.comtrade_code,
        "partnerCode": partner.comtrade_code,
        "cmdCode": hs_code,
        "flowCode": "X" if flow == "export" else "M",
        "period": str(year),
        "maxRecords": str(MAX_RECORDS),
        "includeDesc": "false",
    }


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    body = response.text
    retry_with_key = response.status_code in {401, 403, 429} or _body_requests_key_or_quota(body)
    if response.status_code >= 400:
        raise _UnComtradeApiError("UN Comtrade returned an error status", retry_with_key=retry_with_key)

    try:
        payload = response.json()
    except ValueError as exc:
        raise _UnComtradeApiError("UN Comtrade returned invalid JSON", retry_with_key=retry_with_key) from exc

    if not isinstance(payload, dict):
        raise _UnComtradeApiError("UN Comtrade response did not match expected format")

    error_text = str(payload.get("error") or "")
    rows = payload.get("data")
    if error_text and (not isinstance(rows, list) or not rows):
        raise _UnComtradeApiError(
            "UN Comtrade returned an error payload",
            retry_with_key=_body_requests_key_or_quota(error_text),
        )
    return payload


def _api_record_from_row(row: dict[str, Any], *, default_year: int) -> UnComtradeTradeRecord | None:
    year = _year_from_any(row.get("period")) or _year_from_any(row.get("refYear")) or default_year
    trade_value = _decimal_from_any(row.get("primaryValue"))
    if trade_value is None:
        trade_value = _decimal_from_any(row.get("fobvalue")) or _decimal_from_any(row.get("cifvalue"))
    quantity = _decimal_from_any(row.get("qty"))
    if quantity is None:
        quantity = _decimal_from_any(row.get("altQty")) or _decimal_from_any(row.get("netWgt"))
    if trade_value is None and quantity is None:
        return None
    return UnComtradeTradeRecord(
        year=year,
        trade_value_usd=trade_value,
        quantity=quantity,
        source=API_SOURCE,
    )


def _fallback_records_from_rows(rows: list[dict[str, str]]) -> list[UnComtradeTradeRecord]:
    records = [
        UnComtradeTradeRecord(
            year=int(row["year"]),
            trade_value_usd=_decimal_from_any(row.get("trade_value_usd")),
            quantity=_decimal_from_any(row.get("quantity")),
            source=CSV_FALLBACK_SOURCE,
        )
        for row in rows
        if row.get("year", "").isdigit()
    ]
    return _collapse_records(records, source=CSV_FALLBACK_SOURCE)


def _collapse_records(
    records: list[UnComtradeTradeRecord],
    *,
    source: Literal["api", "csv_fallback"],
) -> list[UnComtradeTradeRecord]:
    grouped: dict[int, tuple[Decimal | None, Decimal | None]] = {}
    for record in records:
        trade_value, quantity = grouped.get(record.year, (None, None))
        grouped[record.year] = (
            _decimal_sum(trade_value, record.trade_value_usd),
            _decimal_sum(quantity, record.quantity),
        )
    return [
        UnComtradeTradeRecord(
            year=year,
            trade_value_usd=values[0],
            quantity=values[1],
            source=source,
        )
        for year, values in sorted(grouped.items())
    ]


def _response(
    reporter: _Country,
    partner: _Country,
    hs_code: str,
    flow: Literal["export", "import"],
    records: list[UnComtradeTradeRecord],
    *,
    fallback_used: bool,
    auth_mode: Literal["no_key", "key", "fallback"],
) -> UnComtradeTradeFlowResponse:
    return UnComtradeTradeFlowResponse(
        hs_code=hs_code,
        reporter=reporter.iso3,
        partner=partner.iso3,
        flow=flow,
        records=records,
        fallback_used=fallback_used,
        auth_mode=auth_mode,
    )


def _normalize_country(value: str) -> _Country:
    normalized = " ".join(value.strip().upper().replace(".", "").split())
    if normalized in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[normalized]
    supported = ", ".join(sorted({"CHN", "USA", "GBR", "JPN", "AUS", "SGP"}))
    raise DataProviderValidationError(f"Unsupported UN Comtrade country: {value}. Supported: {supported}")


def _normalize_flow(value: str) -> Literal["export", "import"]:
    normalized = value.strip().upper()
    if normalized in _FLOW_ALIASES:
        return _FLOW_ALIASES[normalized]
    raise DataProviderValidationError("UN Comtrade flow must be export/import or X/M")


def _normalize_hs_code(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "TOTAL":
        return normalized
    if not normalized or not normalized.isdigit():
        raise DataProviderValidationError("UN Comtrade hs_code must be numeric or TOTAL")
    return normalized


def _validate_year_range(start_year: int, end_year: int) -> None:
    if start_year > end_year:
        raise DataProviderValidationError("UN Comtrade start_year must be less than or equal to end_year")
    if start_year < 1900 or end_year > 2100:
        raise DataProviderValidationError("UN Comtrade year range must stay between 1900 and 2100")


def _row_matches(
    row: dict[str, str],
    reporter: _Country,
    partner: _Country,
    hs_code: str,
    flow: Literal["export", "import"],
    start_year: int,
    end_year: int,
) -> bool:
    try:
        row_year = int(row.get("year", ""))
        row_flow = _normalize_flow(row.get("flow", ""))
    except (DataProviderValidationError, ValueError):
        return False
    return (
        start_year <= row_year <= end_year
        and _country_matches(row.get("reporter", ""), reporter)
        and _country_matches(row.get("partner", ""), partner)
        and row_flow == flow
        and _hs_matches(row.get("hs_code", ""), hs_code)
    )


def _country_matches(row_value: str, expected: _Country) -> bool:
    try:
        return _normalize_country(row_value).iso3 == expected.iso3
    except DataProviderValidationError:
        return False


def _hs_matches(row_value: str, requested_hs_code: str) -> bool:
    row_hs_code = row_value.strip().upper()
    if requested_hs_code == "TOTAL":
        return True
    if len(requested_hs_code) in {2, 4}:
        return row_hs_code.startswith(requested_hs_code)
    return row_hs_code == requested_hs_code


def _read_trade_rows(seed_dir: Path) -> list[dict[str, str]]:
    path = (seed_dir / "trade_samples.csv").resolve()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [_clean_row(row) for row in csv.DictReader(csv_file) if not _is_blank_row(row)]
    except (OSError, csv.Error):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _opposite_flow(flow: Literal["export", "import"]) -> Literal["export", "import"]:
    return "import" if flow == "export" else "export"


def _year_from_any(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _decimal_from_any(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    normalized = str(value).strip().replace(",", "")
    if not normalized:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _decimal_sum(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None:
        return right
    if right is None:
        return left
    return left + right


def _body_requests_key_or_quota(text: str) -> bool:
    normalized = text.casefold()
    markers = (
        "subscription key",
        "subscription-key",
        "ocp-apim-subscription-key",
        "api key",
        "apikey",
        "quota",
        "rate limit",
        "too many requests",
    )
    return any(marker in normalized for marker in markers)
