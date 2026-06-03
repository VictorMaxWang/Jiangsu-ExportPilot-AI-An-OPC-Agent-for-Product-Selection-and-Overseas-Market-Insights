from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas import EtsyListingItem, EtsySearchResponse
from app.services.analysis_performance import is_timeout_error, record_provider_http_call
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE, DataProviderValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEFAULT_ENDPOINT = "https://api.etsy.com/v3/application/listings/active"
DEFAULT_PING_ENDPOINT = "https://api.etsy.com/v3/application/openapi-ping"
MAX_ETSY_RESULTS = 20
ETSY_PLATFORM = "Etsy"
ETSY_SAMPLE_PLATFORM = "Etsy Sample"
ETSY_FALLBACK_PLATFORMS = {ETSY_PLATFORM.casefold(), ETSY_SAMPLE_PLATFORM.casefold()}

COUNTRY_CURRENCY: dict[str, str] = {
    "US": "USD",
    "GB": "GBP",
    "AU": "AUD",
    "CA": "CAD",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "NL": "EUR",
    "JP": "JPY",
    "SG": "SGD",
}

FALLBACK_KEYWORD_ALIASES: dict[str, tuple[str, ...]] = {
    "home textile": (
        "home decor",
        "cotton bedding set",
        "sofa throw",
        "bath towel",
        "cooling quilt",
        "anti mite pillowcase",
        "baby swaddle",
        "dorm room bedding",
        "boho bedroom",
    ),
    "home textiles": (
        "home decor",
        "cotton bedding set",
        "sofa throw",
        "bath towel",
        "cooling quilt",
        "anti mite pillowcase",
        "baby swaddle",
        "dorm room bedding",
        "boho bedroom",
    ),
    "boho blanket": ("boho bedroom", "home decor"),
    "cooling blanket": ("cooling quilt",),
    "pet products": ("pet cooling mat",),
}


ETSY_CREDENTIALS_INVALID_OR_UNAPPROVED = "ETSY_CREDENTIALS_INVALID_OR_UNAPPROVED"
ETSY_LISTINGS_REQUIRES_OAUTH_OR_APPROVAL = "credentials_valid_but_listing_search_requires_oauth_or_approval"
ETSY_LIVE_SEARCH_FAILED = "ETSY_LIVE_SEARCH_FAILED"
ETSY_NOT_CONFIGURED = "ETSY_NOT_CONFIGURED"
ETSY_DISABLED = "ETSY_DISABLED"


class _EtsyApiError(Exception):
    def __init__(self, message: str, *, code: str = ETSY_LIVE_SEARCH_FAILED) -> None:
        self.code = code
        super().__init__(message)


class EtsyProvider:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        ping_endpoint: str = DEFAULT_PING_ENDPOINT,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        seed_dir: Path | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._endpoint = endpoint
        self._ping_endpoint = ping_endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR
        self._clock = clock or _utc_now

    async def search_listings(
        self,
        keyword: str,
        country: str = "US",
        limit: int = MAX_ETSY_RESULTS,
        *,
        allow_fallback: bool = True,
    ) -> EtsySearchResponse:
        normalized_keyword = normalize_keyword(keyword)
        normalized_country = normalize_country(country)
        safe_limit = clamp_limit(limit)
        collected_at = self._clock()

        if not self._settings.enable_etsy:
            if not allow_fallback:
                raise _EtsyApiError("Etsy provider is disabled", code=ETSY_DISABLED)
            return self._fallback_search(normalized_keyword, normalized_country, safe_limit)

        if not self._settings.etsy_keystring or not self._settings.etsy_shared_secret:
            if not allow_fallback:
                raise _EtsyApiError("Etsy credentials are not configured", code=ETSY_NOT_CONFIGURED)
            return self._fallback_search(normalized_keyword, normalized_country, safe_limit)

        try:
            items = await self._fetch_api_items(normalized_keyword, normalized_country, safe_limit, collected_at)
            return EtsySearchResponse(
                keyword=normalized_keyword,
                country=normalized_country,
                items=items,
                fallback_used=False,
            )
        except _EtsyApiError:
            if not allow_fallback:
                raise
            return self._fallback_search(normalized_keyword, normalized_country, safe_limit)

    async def openapi_ping(self) -> bool:
        if not self._settings.enable_etsy:
            raise _EtsyApiError("Etsy provider is disabled", code=ETSY_DISABLED)
        if not self._settings.etsy_keystring or not self._settings.etsy_shared_secret:
            raise _EtsyApiError("Etsy credentials are not configured", code=ETSY_NOT_CONFIGURED)

        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(self._ping_endpoint, headers=self._auth_headers())
        except httpx.HTTPError as exc:
            raise _EtsyApiError("Etsy ping request failed", code=ETSY_LIVE_SEARCH_FAILED) from exc

        if response.status_code >= 400:
            raise _EtsyApiError(
                "Etsy credentials could not be validated",
                code=ETSY_CREDENTIALS_INVALID_OR_UNAPPROVED,
            )
        return True

    async def _fetch_api_items(
        self,
        keyword: str,
        country: str,
        limit: int,
        collected_at: datetime,
    ) -> list[EtsyListingItem]:
        params = {
            "keywords": keyword,
            "limit": str(limit),
            "buyer_country": country,
            "sort_on": "score",
            "sort_order": "desc",
            "is_safe": "true",
        }
        currency = COUNTRY_CURRENCY.get(country)
        if currency:
            params["currency"] = currency

        headers = self._auth_headers()
        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        started_at = datetime.now(timezone.utc)
        start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(self._endpoint, params=params, headers=headers)
        except httpx.HTTPError as exc:
            timeout_error = is_timeout_error(exc)
            record_provider_http_call(
                provider="etsy",
                endpoint="search_competitors_http",
                status="timeout" if timeout_error else "error",
                started_at=started_at,
                duration_ms=max(0, round((perf_counter() - start) * 1000)),
                timeout=timeout_error,
                country=country,
            )
            raise _EtsyApiError("Etsy request failed") from exc

        record_provider_http_call(
            provider="etsy",
            endpoint="search_competitors_http",
            status="success" if response.status_code < 400 else "error",
            started_at=started_at,
            duration_ms=max(0, round((perf_counter() - start) * 1000)),
            country=country,
            http_status=response.status_code,
        )
        if response.status_code >= 400:
            code = (
                ETSY_LISTINGS_REQUIRES_OAUTH_OR_APPROVAL
                if response.status_code in {401, 403} or _body_suggests_oauth_or_approval(response)
                else ETSY_LIVE_SEARCH_FAILED
            )
            raise _EtsyApiError("Etsy returned an error status", code=code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise _EtsyApiError("Etsy returned invalid JSON") from exc

        rows = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise _EtsyApiError("Etsy response did not include results")

        items = [_api_item_from_row(row, keyword, country, collected_at) for row in rows if isinstance(row, dict)]
        normalized_items = [item for item in items if item is not None]
        if not normalized_items:
            raise _EtsyApiError("Etsy returned no usable listings")
        return normalized_items

    def _fallback_search(self, keyword: str, country: str, limit: int) -> EtsySearchResponse:
        rows = _ranked_fallback_rows(keyword, country, self._seed_dir)
        items = [
            item
            for item in (_fallback_item_from_row(row, fallback_keyword=keyword, fallback_country=country) for row in rows[:limit])
            if item is not None
        ]
        return EtsySearchResponse(
            keyword=keyword,
            country=country,
            items=items,
            fallback_used=True,
        )

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "x-api-key": f"{self._settings.etsy_keystring}:{self._settings.etsy_shared_secret}",
        }


def _body_suggests_oauth_or_approval(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    text = str(payload).casefold()
    return any(marker in text for marker in ("oauth", "approval", "approve", "access", "permission"))


def normalize_keyword(keyword: str) -> str:
    normalized = " ".join(keyword.strip().split()).lower()
    if not normalized:
        raise DataProviderValidationError("Etsy keyword must not be empty")
    return normalized


def normalize_country(country: str) -> str:
    normalized = country.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise DataProviderValidationError("Etsy country must be a two-letter ISO country code")
    return normalized


def clamp_limit(limit: int) -> int:
    return min(max(limit, 1), MAX_ETSY_RESULTS)


def etsy_seed_queries(seed_dir: Path | None = None) -> list[tuple[str, str]]:
    pairs = {
        (normalize_keyword(row["keyword"]), normalize_country(row["country"]))
        for row in _read_etsy_sample_rows(seed_dir or DEFAULT_SEED_DIR)
        if row.get("keyword") and row.get("country")
    }
    return sorted(pairs)


def _api_item_from_row(
    row: dict[str, Any],
    keyword: str,
    country: str,
    collected_at: datetime,
) -> EtsyListingItem | None:
    title = _optional_text(row.get("title"))
    if not title:
        return None

    price, currency = _price_and_currency(row)
    shop = row.get("shop") if isinstance(row.get("shop"), dict) else {}
    return EtsyListingItem(
        country=country,
        keyword=keyword,
        title=title,
        price=price,
        currency=currency,
        image_url=_image_url(row),
        product_url=_product_url(row),
        category=_category(row),
        rating=_rating(row, shop),
        review_count=_review_count(row, shop),
        source_type=API_SOURCE,
        collected_at=collected_at,
    )


def _fallback_item_from_row(
    row: dict[str, str],
    *,
    fallback_keyword: str,
    fallback_country: str,
) -> EtsyListingItem | None:
    title = row.get("title")
    if not title:
        return None
    return EtsyListingItem(
        country=(row.get("country") or fallback_country).upper(),
        keyword=row.get("keyword") or fallback_keyword,
        title=title,
        price=_decimal_from_any(row.get("price")),
        currency=(row.get("currency") or None),
        image_url=row.get("image_url") or None,
        product_url=row.get("product_url") or None,
        category=row.get("category") or None,
        rating=_decimal_from_any(row.get("rating")),
        review_count=_int_from_any(row.get("review_count")),
        source_type=CSV_FALLBACK_SOURCE,
        collected_at=_parse_datetime(row.get("collected_at")),
    )


def _price_and_currency(row: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    for key in ("converted_price", "price"):
        price, currency = _money_value(row.get(key))
        if price is not None or currency is not None:
            return price, currency
    return None, _optional_text(row.get("currency_code"))


def _money_value(value: Any) -> tuple[Decimal | None, str | None]:
    if isinstance(value, dict):
        currency = _optional_text(value.get("currency_code")) or _optional_text(value.get("currency"))
        amount = _decimal_from_any(value.get("amount"))
        divisor = _decimal_from_any(value.get("divisor"))
        if amount is not None and divisor not in (None, Decimal("0")):
            return amount / divisor, currency
        for key in ("value", "price"):
            parsed = _decimal_from_any(value.get(key))
            if parsed is not None:
                return parsed, currency
        return None, currency
    return _decimal_from_any(value), None


def _image_url(row: dict[str, Any]) -> str | None:
    direct = _optional_text(row.get("image_url"))
    if direct:
        return direct

    images = row.get("images") or row.get("Images")
    if not isinstance(images, list):
        return None
    image_rows = [image for image in images if isinstance(image, dict)]
    image_rows.sort(key=_image_rank)
    for image in image_rows:
        for key in ("url_fullxfull", "url_570xN", "url_170x135", "url_75x75"):
            url = _optional_text(image.get(key))
            if url:
                return url
    return None


def _image_rank(image: dict[str, Any]) -> int:
    rank = _int_from_any(image.get("rank"))
    return rank if rank is not None else 10_000


def _product_url(row: dict[str, Any]) -> str | None:
    url = _optional_text(row.get("url")) or _optional_text(row.get("product_url"))
    if url:
        return url
    listing_id = _optional_text(row.get("listing_id"))
    if listing_id:
        return f"https://www.etsy.com/listing/{listing_id}"
    return None


def _category(row: dict[str, Any]) -> str | None:
    taxonomy_path = row.get("taxonomy_path")
    if isinstance(taxonomy_path, list):
        parts = [str(part).strip() for part in taxonomy_path if str(part).strip()]
        return " > ".join(parts) or None
    return _optional_text(taxonomy_path) or _optional_text(row.get("category"))


def _rating(row: dict[str, Any], shop: dict[str, Any]) -> Decimal | None:
    for value in (shop.get("review_average"), row.get("review_average"), row.get("rating")):
        parsed = _decimal_from_any(value)
        if parsed is not None:
            return parsed
    return None


def _review_count(row: dict[str, Any], shop: dict[str, Any]) -> int | None:
    for value in (shop.get("review_count"), row.get("review_count")):
        parsed = _int_from_any(value)
        if parsed is not None:
            return parsed
    return None


def _ranked_fallback_rows(keyword: str, country: str, seed_dir: Path) -> list[dict[str, str]]:
    aliases = {keyword, *FALLBACK_KEYWORD_ALIASES.get(keyword, ())}
    ranked: list[tuple[int, Decimal, int, datetime, dict[str, str]]] = []
    seen_urls: set[str] = set()

    for row in _read_etsy_sample_rows(seed_dir):
        url = row.get("product_url", "")
        if url and url in seen_urls:
            continue
        row_keyword = normalize_keyword(row.get("keyword", ""))
        row_country = row.get("country", "").upper()
        keyword_match = row_keyword in aliases
        country_match = row_country == country
        if keyword_match and country_match:
            rank = 0
        elif keyword_match:
            rank = 1
        elif country_match:
            rank = 2
        else:
            rank = 3
        ranked.append(
            (
                rank,
                _decimal_from_any(row.get("rating")) or Decimal("0"),
                _int_from_any(row.get("review_count")) or 0,
                _parse_datetime(row.get("collected_at")) or datetime.min.replace(tzinfo=timezone.utc),
                row,
            )
        )
        if url:
            seen_urls.add(url)

    ranked.sort(key=lambda item: (item[0], -item[1], -item[2], _reverse_datetime_key(item[3])))
    return [row for _rank, _rating_value, _reviews, _collected_at, row in ranked]


def _read_etsy_sample_rows(seed_dir: Path) -> list[dict[str, str]]:
    path = (seed_dir / "competitor_samples.csv").resolve()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [
                row
                for row in (_clean_row(raw_row) for raw_row in csv.DictReader(csv_file))
                if row.get("platform", "").casefold() in ETSY_FALLBACK_PLATFORMS
            ]
    except (OSError, csv.Error):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _decimal_from_any(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return None
        try:
            return Decimal(normalized)
        except InvalidOperation:
            return None
    return None


def _int_from_any(value: Any) -> int | None:
    parsed = _decimal_from_any(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (OverflowError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _reverse_datetime_key(value: datetime) -> tuple[int, int, int, int, int, int, int]:
    return (
        -value.year,
        -value.month,
        -value.day,
        -value.hour,
        -value.minute,
        -value.second,
        -value.microsecond,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
