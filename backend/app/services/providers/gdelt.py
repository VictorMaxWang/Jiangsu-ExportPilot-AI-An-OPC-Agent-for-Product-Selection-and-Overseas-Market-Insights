from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

import httpx

from app.schemas import GdeltArticleItem, GdeltSearchResponse
from app.services.analysis_performance import is_timeout_error, record_provider_http_call
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE, DataProviderValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEFAULT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

SUPPORTED_KEYWORDS: tuple[str, ...] = (
    "home textile",
    "pet products",
    "home decor",
    "cross border e-commerce",
    "China textile export",
    "dorm room bedding",
    "boho bedroom",
)

_KEYWORD_BY_NORMALIZED = {keyword.lower(): keyword for keyword in SUPPORTED_KEYWORDS}

SUPPORTED_COUNTRIES: dict[str, str] = {
    "US": "unitedstates",
    "GB": "unitedkingdom",
    "JP": "japan",
    "AU": "australia",
    "SG": "singapore",
    "CN": "china",
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
    "pet products": ("pet cooling mat",),
    "home decor": ("home decor",),
    "cross border e-commerce": (
        "home decor",
        "dorm room bedding",
        "boho bedroom",
        "pet cooling mat",
    ),
    "China textile export": (
        "home decor",
        "cotton bedding set",
        "sofa throw",
        "dorm room bedding",
        "boho bedroom",
    ),
    "dorm room bedding": ("dorm room bedding",),
    "boho bedroom": ("boho bedroom",),
}


class _GdeltApiError(Exception):
    pass


class GdeltProvider:
    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def search(
        self,
        query: str,
        *,
        country: str | None = None,
        max_records: int = 10,
    ) -> GdeltSearchResponse:
        normalized_query = _normalize_keyword(query)
        normalized_country = _normalize_country(country) if country else None
        safe_max_records = min(max(max_records, 1), 250)
        try:
            items = await self._fetch_api_items(normalized_query, normalized_country, safe_max_records)
            return GdeltSearchResponse(
                query=normalized_query,
                items=items,
                fallback_used=False,
            )
        except _GdeltApiError:
            return self._fallback_search(normalized_query, normalized_country, safe_max_records)

    async def _fetch_api_items(
        self,
        query: str,
        country: str | None,
        max_records: int,
    ) -> list[GdeltArticleItem]:
        gdelt_query = f'"{query}"'
        if country:
            gdelt_query = f"{gdelt_query} sourcecountry:{SUPPORTED_COUNTRIES[country]}"

        params = {
            "query": gdelt_query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(max_records),
            "timespan": "1month",
            "sort": "datedesc",
        }
        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        started_at = datetime.now(timezone.utc)
        start = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(self._endpoint, params=params)
        except httpx.HTTPError as exc:
            timeout_error = is_timeout_error(exc)
            record_provider_http_call(
                provider="gdelt",
                endpoint="search_news_trends_http",
                status="timeout" if timeout_error else "error",
                started_at=started_at,
                duration_ms=max(0, round((perf_counter() - start) * 1000)),
                timeout=timeout_error,
                country=country,
            )
            raise _GdeltApiError("GDELT request failed") from exc

        record_provider_http_call(
            provider="gdelt",
            endpoint="search_news_trends_http",
            status="success" if response.status_code < 400 else "error",
            started_at=started_at,
            duration_ms=max(0, round((perf_counter() - start) * 1000)),
            country=country,
            http_status=response.status_code,
        )
        if response.status_code >= 400:
            raise _GdeltApiError("GDELT returned an error status")

        try:
            payload = response.json()
        except ValueError as exc:
            raise _GdeltApiError("GDELT returned invalid JSON") from exc

        articles = payload.get("articles") if isinstance(payload, dict) else None
        if not isinstance(articles, list):
            raise _GdeltApiError("GDELT response did not include article list")

        items = [_api_item_from_article(article) for article in articles if isinstance(article, dict)]
        normalized_items = [item for item in items if item is not None]
        if not normalized_items:
            raise _GdeltApiError("GDELT returned no usable articles")
        return normalized_items

    def _fallback_search(
        self,
        query: str,
        country: str | None,
        max_records: int,
    ) -> GdeltSearchResponse:
        keywords = {keyword.lower() for keyword in FALLBACK_KEYWORD_ALIASES[query]}
        rows = [
            row
            for row in _read_content_trends(self._seed_dir)
            if row.get("keyword", "").lower() in keywords
            and (country is None or row.get("country", "").upper() == country)
        ]
        rows.sort(key=lambda row: _heat_score(row.get("heat_score")), reverse=True)
        items = [
            GdeltArticleItem(
                title=row["title"],
                url=row["url"],
                domain=_domain_from_url(row.get("url")),
                published_at=row.get("published_at") or None,
                language="und",
                source=CSV_FALLBACK_SOURCE,
            )
            for row in rows[:max_records]
            if row.get("title") and row.get("url")
        ]
        return GdeltSearchResponse(
            query=query,
            items=items,
            fallback_used=True,
        )


def _normalize_keyword(query: str) -> str:
    normalized = " ".join(query.strip().split()).lower()
    if normalized not in _KEYWORD_BY_NORMALIZED:
        supported = ", ".join(SUPPORTED_KEYWORDS)
        raise DataProviderValidationError(f"Unsupported GDELT query: {query}. Supported: {supported}")
    return _KEYWORD_BY_NORMALIZED[normalized]


def _normalize_country(country: str) -> str:
    normalized = country.strip().upper()
    if normalized not in SUPPORTED_COUNTRIES:
        supported = ", ".join(SUPPORTED_COUNTRIES)
        raise DataProviderValidationError(f"Unsupported GDELT country: {country}. Supported: {supported}")
    return normalized


def _api_item_from_article(article: dict[str, Any]) -> GdeltArticleItem | None:
    title = str(article.get("title") or "").strip()
    url = str(article.get("url") or "").strip()
    if not title or not url:
        return None
    domain = str(article.get("domain") or "").strip() or _domain_from_url(url)
    language = article.get("language")
    return GdeltArticleItem(
        title=title,
        url=url,
        domain=domain,
        published_at=_parse_gdelt_datetime(article.get("seendate")),
        language=str(language).strip() if language else None,
        source=API_SOURCE,
    )


def _parse_gdelt_datetime(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    for pattern in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            parsed = datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        except ValueError:
            continue
    return raw or None


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


def _read_content_trends(seed_dir: Path) -> list[dict[str, str]]:
    path = (seed_dir / "content_trends.csv").resolve()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [_clean_row(row) for row in csv.DictReader(csv_file) if not _is_blank_row(row)]
    except (OSError, csv.Error):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _heat_score(value: str | None) -> Decimal:
    if value is None or not value.strip():
        return Decimal("0")
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")
