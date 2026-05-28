from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import YoutubeSearchCache
from app.schemas import YoutubeSearchResponse, YoutubeVideoItem
from app.services.providers import API_SOURCE
from app.services.providers.youtube import (
    MAX_YOUTUBE_RESULTS,
    YoutubeProvider,
    clamp_max_results,
    normalize_country,
    normalize_keyword,
)


CACHE_TTL = timedelta(hours=24)


class YoutubeSearchCacheService:
    def __init__(
        self,
        db: Session,
        *,
        provider: YoutubeProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._provider = provider or YoutubeProvider(settings=self._settings)

    async def search_videos(
        self,
        keyword: str,
        country: str = "US",
        limit: int = MAX_YOUTUBE_RESULTS,
    ) -> YoutubeSearchResponse:
        normalized_keyword = normalize_keyword(keyword)
        normalized_country = normalize_country(country)
        safe_limit = clamp_max_results(limit)

        if self._cache_enabled():
            cached = self._read_cache(normalized_keyword, normalized_country, safe_limit)
            if cached is not None:
                return cached

        response = await self._provider.search_videos(
            normalized_keyword,
            country=normalized_country,
            max_results=MAX_YOUTUBE_RESULTS,
        )
        if self._cache_enabled() and not response.fallback_used:
            self._write_cache(response)
        return _limited_response(response, safe_limit)

    def _cache_enabled(self) -> bool:
        return bool(self._settings.enable_youtube and self._settings.youtube_data_api_key)

    def _read_cache(
        self,
        keyword: str,
        country: str,
        limit: int,
    ) -> YoutubeSearchResponse | None:
        now = datetime.now(timezone.utc)
        cache = self._db.scalar(
            select(YoutubeSearchCache).where(
                YoutubeSearchCache.keyword == keyword,
                YoutubeSearchCache.country == country,
                YoutubeSearchCache.expires_at > now,
            )
        )
        if cache is None:
            return None

        try:
            items = [YoutubeVideoItem.model_validate(item) for item in cache.items]
        except (TypeError, ValueError):
            return None
        return YoutubeSearchResponse(
            keyword=keyword,
            country=country,
            items=items[:limit],
            fallback_used=False,
        )

    def _write_cache(self, response: YoutubeSearchResponse) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + CACHE_TTL
        items = [item.model_dump(mode="json") for item in response.items]
        try:
            existing = self._db.scalar(
                select(YoutubeSearchCache).where(
                    YoutubeSearchCache.keyword == response.keyword,
                    YoutubeSearchCache.country == response.country,
                )
            )
            if existing is None:
                self._db.add(
                    YoutubeSearchCache(
                        keyword=response.keyword,
                        country=response.country,
                        source=API_SOURCE,
                        items=items,
                        fetched_at=now,
                        expires_at=expires_at,
                    )
                )
            else:
                existing.source = API_SOURCE
                existing.items = items
                existing.fetched_at = now
                existing.expires_at = expires_at
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()


def _limited_response(response: YoutubeSearchResponse, limit: int) -> YoutubeSearchResponse:
    return YoutubeSearchResponse(
        keyword=response.keyword,
        country=response.country,
        items=response.items[:limit],
        fallback_used=response.fallback_used,
    )
