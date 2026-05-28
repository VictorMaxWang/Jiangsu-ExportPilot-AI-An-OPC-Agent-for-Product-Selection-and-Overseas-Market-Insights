from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas import YoutubeSearchResponse, YoutubeVideoItem
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE, DataProviderValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
DEFAULT_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
MAX_YOUTUBE_RESULTS = 10
YOUTUBE_PLATFORM = "YouTube"
YOUTUBE_SAMPLE_PLATFORM = "YouTube Sample"

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
    "cooling blanket": ("cooling quilt",),
}


class _YoutubeApiError(Exception):
    pass


class YoutubeProvider:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def search_videos(
        self,
        keyword: str,
        country: str = "US",
        max_results: int = MAX_YOUTUBE_RESULTS,
        *,
        allow_fallback: bool = True,
    ) -> YoutubeSearchResponse:
        normalized_keyword = normalize_keyword(keyword)
        normalized_country = normalize_country(country)
        safe_max_results = clamp_max_results(max_results)

        if not self._settings.enable_youtube:
            if not allow_fallback:
                raise _YoutubeApiError("YOUTUBE_DISABLED")
            return self._fallback_search(normalized_keyword, normalized_country, safe_max_results)

        if not self._settings.youtube_data_api_key:
            if not allow_fallback:
                raise _YoutubeApiError("YOUTUBE_NOT_CONFIGURED")
            return self._fallback_search(normalized_keyword, normalized_country, safe_max_results)

        try:
            items = await self._fetch_api_items(normalized_keyword, normalized_country, safe_max_results)
            return YoutubeSearchResponse(
                keyword=normalized_keyword,
                country=normalized_country,
                items=items,
                fallback_used=False,
            )
        except _YoutubeApiError:
            if not allow_fallback:
                raise
            return self._fallback_search(normalized_keyword, normalized_country, safe_max_results)

    async def _fetch_api_items(
        self,
        keyword: str,
        country: str,
        max_results: int,
    ) -> list[YoutubeVideoItem]:
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": str(max_results),
            "relevanceLanguage": "en",
            "regionCode": country,
            "key": self._settings.youtube_data_api_key,
        }
        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.get(self._endpoint, params=params)
        except httpx.HTTPError as exc:
            raise _YoutubeApiError("YouTube request failed") from exc

        if response.status_code >= 400:
            raise _YoutubeApiError("YouTube returned an error status")

        try:
            payload = response.json()
        except ValueError as exc:
            raise _YoutubeApiError("YouTube returned invalid JSON") from exc

        rows = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise _YoutubeApiError("YouTube response did not include item list")

        items = [_api_item_from_row(row, keyword, country) for row in rows if isinstance(row, dict)]
        normalized_items = [item for item in items if item is not None]
        if not normalized_items:
            raise _YoutubeApiError("YouTube returned no usable videos")
        return normalized_items

    def _fallback_search(
        self,
        keyword: str,
        country: str,
        max_results: int,
    ) -> YoutubeSearchResponse:
        rows = _ranked_fallback_rows(keyword, country, self._seed_dir)
        items = [
            YoutubeVideoItem(
                country=row.get("country", country).upper() or country,
                keyword=row.get("keyword") or keyword,
                title=row["title"],
                channel_title=row.get("channel_or_community") or None,
                published_at=row.get("published_at") or None,
                thumbnail_url=None,
                video_url=row.get("url") or None,
                description=row.get("summary") or None,
                source_type=CSV_FALLBACK_SOURCE,
            )
            for row in rows[:max_results]
            if row.get("title")
        ]
        return YoutubeSearchResponse(
            keyword=keyword,
            country=country,
            items=items,
            fallback_used=True,
        )


def normalize_keyword(keyword: str) -> str:
    normalized = " ".join(keyword.strip().split()).lower()
    if not normalized:
        raise DataProviderValidationError("YouTube keyword must not be empty")
    return normalized


def normalize_country(country: str) -> str:
    normalized = country.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise DataProviderValidationError("YouTube country must be a two-letter ISO country code")
    return normalized


def clamp_max_results(max_results: int) -> int:
    return min(max(max_results, 1), MAX_YOUTUBE_RESULTS)


def youtube_seed_queries(seed_dir: Path | None = None) -> list[tuple[str, str]]:
    pairs = {
        (normalize_keyword(row["keyword"]), normalize_country(row["country"]))
        for row in _read_youtube_sample_rows(seed_dir or DEFAULT_SEED_DIR)
        if row.get("keyword") and row.get("country")
    }
    return sorted(pairs)


def _api_item_from_row(row: dict[str, Any], keyword: str, country: str) -> YoutubeVideoItem | None:
    video_id = _video_id(row.get("id"))
    snippet = row.get("snippet")
    if not video_id or not isinstance(snippet, dict):
        return None

    title = str(snippet.get("title") or "").strip()
    if not title:
        return None

    return YoutubeVideoItem(
        country=country,
        keyword=keyword,
        title=title,
        channel_title=_optional_text(snippet.get("channelTitle")),
        published_at=_optional_text(snippet.get("publishedAt")),
        thumbnail_url=_thumbnail_url(snippet.get("thumbnails")),
        video_url=f"https://www.youtube.com/watch?v={video_id}",
        description=_optional_text(snippet.get("description")),
        source_type=API_SOURCE,
    )


def _video_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("videoId")
    if raw is None:
        return None
    video_id = str(raw).strip()
    return video_id or None


def _thumbnail_url(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("high", "medium", "default"):
        candidate = value.get(key)
        if isinstance(candidate, dict):
            url = _optional_text(candidate.get("url"))
            if url:
                return url
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ranked_fallback_rows(keyword: str, country: str, seed_dir: Path) -> list[dict[str, str]]:
    aliases = {keyword, *FALLBACK_KEYWORD_ALIASES.get(keyword, ())}
    ranked: list[tuple[int, Decimal, datetime, dict[str, str]]] = []
    seen_urls: set[str] = set()

    for row in _read_youtube_sample_rows(seed_dir):
        url = row.get("url", "")
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
        ranked.append((rank, _heat_score(row.get("heat_score")), _published_at(row.get("published_at")), row))
        if url:
            seen_urls.add(url)

    ranked.sort(key=lambda item: (item[0], -item[1], -item[2].timestamp()))
    return [row for _rank, _heat, _published, row in ranked]


def _read_youtube_sample_rows(seed_dir: Path) -> list[dict[str, str]]:
    path = (seed_dir / "content_trends.csv").resolve()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [
                row
                for row in (_clean_row(raw_row) for raw_row in csv.DictReader(csv_file))
                if row.get("platform", "").casefold() == YOUTUBE_SAMPLE_PLATFORM.casefold()
            ]
    except (OSError, csv.Error):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _heat_score(value: str | None) -> Decimal:
    if value is None or not value.strip():
        return Decimal("0")
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")


def _published_at(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
