from __future__ import annotations

import csv
import json
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any, TypeVar
from urllib.parse import urlparse

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import get_db
from app.models import ApiCallLog, DataSourceCache
from app.schemas import (
    DataSourceCompetitorItem,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendItem,
    DataSourceContentTrendResponse,
    EtsySearchResponse,
    GdeltArticleItem,
    GdeltSearchResponse,
    UnComtradeTradeFlowResponse,
    UnComtradeTradeRecord,
    WorldBankCountryResponse,
    WorldBankIndicatorItem,
    YoutubeSearchResponse,
)
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE
from app.services.providers.etsy import EtsyProvider, clamp_limit as clamp_etsy_limit
from app.services.providers.gdelt import GdeltProvider
from app.services.providers.un_comtrade import UnComtradeProvider
from app.services.providers.worldbank import SUPPORTED_INDICATORS, WorldBankProvider
from app.services.providers.youtube import (
    MAX_YOUTUBE_RESULTS,
    YoutubeProvider,
    clamp_max_results as clamp_youtube_limit,
    normalize_country as normalize_youtube_country,
    normalize_keyword as normalize_youtube_keyword,
)
from app.utils.redaction import redact_mapping, redact_text


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
CACHE_TTL = timedelta(hours=24)
GLOBAL_COUNTRY = "GLOBAL"
DEFAULT_COUNTRY = "US"
DEFAULT_TRADE_START_YEAR = 2020
DEFAULT_TRADE_END_YEAR = 2024

T = TypeVar("T", bound=BaseModel)


class DataSourceService:
    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        worldbank_provider: WorldBankProvider | None = None,
        gdelt_provider: GdeltProvider | None = None,
        youtube_provider: YoutubeProvider | None = None,
        etsy_provider: EtsyProvider | None = None,
        un_comtrade_provider: UnComtradeProvider | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR
        self._worldbank_provider = worldbank_provider or WorldBankProvider(seed_dir=self._seed_dir)
        self._gdelt_provider = gdelt_provider or GdeltProvider(seed_dir=self._seed_dir)
        self._youtube_provider = youtube_provider or YoutubeProvider(settings=self._settings, seed_dir=self._seed_dir)
        self._etsy_provider = etsy_provider or EtsyProvider(settings=self._settings, seed_dir=self._seed_dir)
        self._un_comtrade_provider = un_comtrade_provider or UnComtradeProvider(
            settings=self._settings,
            seed_dir=self._seed_dir,
        )

    async def get_market_profile(self, country_code: str) -> WorldBankCountryResponse:
        normalized_country = _normalize_country_key(country_code)
        return await self._cached_call(
            provider="worldbank",
            endpoint="market_profile",
            query_key="market_profile",
            country_key=normalized_country,
            response_model=WorldBankCountryResponse,
            query_log={"country_code": normalized_country},
            producer=lambda: self._get_market_profile_uncached(normalized_country),
        )

    async def search_news_trends(
        self,
        query: str,
        country: str | None = None,
        *,
        limit: int = 10,
    ) -> GdeltSearchResponse:
        normalized_query = _normalize_text(query)
        normalized_country = _normalize_optional_country(country)
        safe_limit = _clamp(limit, 1, 250)
        response = await self._cached_call(
            provider="gdelt",
            endpoint="search_news_trends",
            query_key=normalized_query,
            country_key=normalized_country or GLOBAL_COUNTRY,
            response_model=GdeltSearchResponse,
            query_log={"query": normalized_query, "country": normalized_country, "limit": safe_limit},
            producer=lambda: self._search_news_trends_uncached(normalized_query, normalized_country, 50),
        )
        return _limit_gdelt_response(response, safe_limit)

    async def search_video_trends(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 10,
        force_live: bool = False,
    ) -> YoutubeSearchResponse:
        normalized_keyword = normalize_youtube_keyword(keyword)
        normalized_country = normalize_youtube_country(country or DEFAULT_COUNTRY)
        safe_limit = clamp_youtube_limit(limit)
        response = await self._cached_call(
            provider="youtube",
            endpoint="search_video_trends",
            query_key=normalized_keyword,
            country_key=normalized_country,
            response_model=YoutubeSearchResponse,
            query_log={"keyword": normalized_keyword, "country": normalized_country, "limit": safe_limit},
            producer=lambda: self._search_video_trends_uncached(normalized_keyword, normalized_country, MAX_YOUTUBE_RESULTS),
            force_live=force_live,
        )
        return _limit_youtube_response(response, safe_limit)

    async def search_competitors(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 20,
        force_live: bool = False,
    ) -> DataSourceCompetitorSearchResponse:
        normalized_keyword = _normalize_text(keyword)
        normalized_country = _normalize_optional_country(country) or DEFAULT_COUNTRY
        safe_limit = _clamp(limit, 1, 50)
        response = await self._cached_call(
            provider="etsy",
            endpoint="search_competitors",
            query_key=normalized_keyword,
            country_key=normalized_country,
            response_model=DataSourceCompetitorSearchResponse,
            query_log={"keyword": normalized_keyword, "country": normalized_country, "limit": safe_limit},
            producer=lambda: self._search_competitors_uncached(normalized_keyword, normalized_country, 50),
            force_live=force_live,
        )
        return _limit_competitor_response(response, safe_limit)

    async def get_trade_data(
        self,
        product_category: str,
        hs_code: str | None = None,
        country: str | None = None,
        *,
        force_live: bool = False,
    ) -> UnComtradeTradeFlowResponse:
        normalized_category = _normalize_text(product_category)
        normalized_country = _normalize_optional_country(country) or DEFAULT_COUNTRY
        normalized_hs_code = _normalize_hs_code(hs_code) if hs_code else _infer_hs_code(normalized_category)
        return await self._cached_call(
            provider="un_comtrade",
            endpoint="trade_data",
            query_key=f"category:{normalized_category}|hs:{normalized_hs_code}",
            country_key=normalized_country,
            response_model=UnComtradeTradeFlowResponse,
            query_log={
                "product_category": normalized_category,
                "hs_code": normalized_hs_code,
                "country": normalized_country,
                "reporter": "CHN",
                "flow": "export",
            },
            producer=lambda: self._get_trade_data_uncached(
                normalized_category,
                normalized_hs_code,
                normalized_country,
            ),
            force_live=force_live,
        )

    async def get_content_trends(
        self,
        keyword: str,
        country: str | None = None,
        *,
        limit: int = 20,
        force_live: bool = False,
    ) -> DataSourceContentTrendResponse:
        normalized_keyword = _normalize_text(keyword)
        normalized_country = _normalize_optional_country(country)
        safe_limit = _clamp(limit, 1, 50)
        response = await self._cached_call(
            provider="data_source_service",
            endpoint="content_trends",
            query_key=normalized_keyword,
            country_key=normalized_country or GLOBAL_COUNTRY,
            response_model=DataSourceContentTrendResponse,
            query_log={"keyword": normalized_keyword, "country": normalized_country, "limit": safe_limit},
            producer=lambda: self._get_content_trends_uncached(normalized_keyword, normalized_country, 50, force_live=force_live),
            force_live=force_live,
        )
        return _limit_content_response(response, safe_limit)

    async def _get_market_profile_uncached(self, country_code: str) -> WorldBankCountryResponse:
        try:
            return await self._worldbank_provider.fetch_country(country_code)
        except Exception:
            return _fallback_market_profile(country_code, self._seed_dir)

    async def _search_news_trends_uncached(
        self,
        query: str,
        country: str | None,
        limit: int,
    ) -> GdeltSearchResponse:
        try:
            response = await self._gdelt_provider.search(query, country=country, max_records=limit)
            if not response.fallback_used:
                return response
        except Exception:
            pass
        return _fallback_gdelt_search(query, country, limit, self._seed_dir)

    async def _search_video_trends_uncached(
        self,
        keyword: str,
        country: str,
        limit: int,
    ) -> YoutubeSearchResponse:
        try:
            response = await self._youtube_provider.search_videos(
                keyword,
                country=country,
                max_results=min(limit, MAX_YOUTUBE_RESULTS),
            )
            if response.items:
                return _limit_youtube_response(response, limit)
        except Exception:
            pass
        return _fallback_youtube_search(keyword, country, limit, self._seed_dir)

    async def _search_competitors_uncached(
        self,
        keyword: str,
        country: str,
        limit: int,
    ) -> DataSourceCompetitorSearchResponse:
        try:
            response = await self._etsy_provider.search_listings(keyword, country=country, limit=clamp_etsy_limit(limit))
            if not response.fallback_used:
                return _competitor_response_from_etsy(response, limit)
        except Exception:
            pass
        return _fallback_competitor_search(keyword, country, limit, self._seed_dir)

    async def _get_trade_data_uncached(
        self,
        product_category: str,
        hs_code: str,
        country: str,
    ) -> UnComtradeTradeFlowResponse:
        try:
            return await self._un_comtrade_provider.get_trade_flow(
                reporter="CHN",
                partner=country,
                hs_code=hs_code,
                flow="export",
                start_year=DEFAULT_TRADE_START_YEAR,
                end_year=DEFAULT_TRADE_END_YEAR,
            )
        except Exception:
            return _fallback_trade_data(product_category, hs_code, country, self._seed_dir)

    async def _get_content_trends_uncached(
        self,
        keyword: str,
        country: str | None,
        limit: int,
        *,
        force_live: bool = False,
    ) -> DataSourceContentTrendResponse:
        items: list[DataSourceContentTrendItem] = []
        sources: set[str] = set()
        fallback_used = False

        try:
            youtube = await self.search_video_trends(
                keyword,
                country=country or DEFAULT_COUNTRY,
                limit=10,
                force_live=force_live,
            )
            fallback_used = fallback_used or youtube.fallback_used
            for item in youtube.items:
                sources.add(item.platform)
                items.append(
                    DataSourceContentTrendItem(
                        platform=item.platform,
                        country=item.country,
                        keyword=item.keyword,
                        title=item.title,
                        url=item.video_url,
                        channel_or_community=item.channel_title,
                        published_at=item.published_at,
                        summary=item.description,
                        content_style=item.source_type,
                        source_type=item.source_type,
                    )
                )
        except Exception:
            fallback_used = True

        try:
            gdelt = await self.search_news_trends(keyword, country=country, limit=10)
            fallback_used = fallback_used or gdelt.fallback_used
            for item in gdelt.items:
                sources.add("GDELT")
                items.append(
                    DataSourceContentTrendItem(
                        platform="GDELT",
                        country=country,
                        keyword=gdelt.query,
                        title=item.title,
                        url=item.url,
                        channel_or_community=item.domain,
                        published_at=item.published_at,
                        summary=None,
                        content_style=item.language,
                        source_type=item.source,
                    )
                )
        except Exception:
            fallback_used = True

        csv_items = _fallback_content_trend_items(keyword, country, limit, self._seed_dir)
        for item in csv_items:
            sources.add(item.platform)
        items.extend(csv_items)

        deduped = _dedupe_content_items(items)
        deduped.sort(key=_content_sort_key)
        return DataSourceContentTrendResponse(
            keyword=keyword,
            country=country,
            items=deduped[:limit],
            fallback_used=fallback_used,
            sources=sorted(sources),
        )

    async def _cached_call(
        self,
        *,
        provider: str,
        endpoint: str,
        query_key: str,
        country_key: str,
        response_model: type[T],
        query_log: dict[str, object],
        producer: Callable[[], Coroutine[Any, Any, T]],
        force_live: bool = False,
    ) -> T:
        start = perf_counter()
        cached = None if force_live else self._read_cache(provider, endpoint, query_key, country_key, response_model)
        if cached is not None:
            self._write_log(
                provider=provider,
                endpoint=endpoint,
                query=query_log,
                status="cache_hit",
                response_time_ms=_elapsed_ms(start),
                fallback_used=bool(getattr(cached, "fallback_used", False)),
                error_message=None,
            )
            return cached

        response = await producer()
        fallback_used = bool(getattr(response, "fallback_used", False))
        source = _response_source(response)
        self._write_cache(provider, endpoint, query_key, country_key, response, fallback_used, source)
        self._write_log(
            provider=provider,
            endpoint=endpoint,
            query=query_log,
            status="fallback" if fallback_used else "success",
            response_time_ms=_elapsed_ms(start),
            fallback_used=fallback_used,
            error_message="Provider failed or unavailable; CSV fallback used." if fallback_used else None,
        )
        return response

    def _read_cache(
        self,
        provider: str,
        endpoint: str,
        query: str,
        country: str,
        response_model: type[T],
    ) -> T | None:
        now = _utc_now()
        cache = self._db.scalar(
            select(DataSourceCache).where(
                DataSourceCache.provider == provider,
                DataSourceCache.endpoint == endpoint,
                DataSourceCache.query == query,
                DataSourceCache.country == country,
                DataSourceCache.expires_at > now,
            )
        )
        if cache is None:
            return None
        try:
            return response_model.model_validate(cache.response_payload)
        except (TypeError, ValueError):
            return None

    def _write_cache(
        self,
        provider: str,
        endpoint: str,
        query: str,
        country: str,
        response: BaseModel,
        fallback_used: bool,
        source: str,
    ) -> None:
        now = _utc_now()
        payload = response.model_dump(mode="json")
        try:
            existing = self._db.scalar(
                select(DataSourceCache).where(
                    DataSourceCache.provider == provider,
                    DataSourceCache.endpoint == endpoint,
                    DataSourceCache.query == query,
                    DataSourceCache.country == country,
                )
            )
            if existing is None:
                self._db.add(
                    DataSourceCache(
                        provider=provider,
                        endpoint=endpoint,
                        query=query,
                        country=country,
                        response_payload=payload,
                        fallback_used=fallback_used,
                        source=source,
                        fetched_at=now,
                        expires_at=now + CACHE_TTL,
                    )
                )
            else:
                existing.response_payload = payload
                existing.fallback_used = fallback_used
                existing.source = source
                existing.fetched_at = now
                existing.expires_at = now + CACHE_TTL
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()

    def _write_log(
        self,
        *,
        provider: str,
        endpoint: str,
        query: dict[str, object],
        status: str,
        response_time_ms: int,
        fallback_used: bool,
        error_message: str | None,
    ) -> None:
        try:
            self._db.add(
                ApiCallLog(
                    provider=provider,
                    endpoint=endpoint,
                    query=_safe_query_json(query),
                    status=status,
                    response_time_ms=response_time_ms,
                    fallback_used=fallback_used,
                    error_message=_safe_error_message(error_message),
                    called_at=_utc_now(),
                )
            )
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()


def get_data_source_service(db: Session = Depends(get_db)) -> DataSourceService:
    return DataSourceService(db)


def _fallback_market_profile(country_code: str, seed_dir: Path) -> WorldBankCountryResponse:
    row = _find_row(seed_dir / "market_profiles.csv", lambda item: item.get("country_code", "").upper() == country_code)
    if row is None:
        return WorldBankCountryResponse(country_code=country_code, indicators=[], fallback_used=True)

    gdp_per_capita = _decimal_from_any(row.get("gdp_per_capita"))
    population = _decimal_from_any(row.get("population"))
    internet_penetration = _decimal_from_any(row.get("internet_penetration"))
    indicators: list[WorldBankIndicatorItem] = []
    if gdp_per_capita is not None and population is not None:
        indicators.append(_worldbank_fallback_indicator("NY.GDP.MKTP.CD", gdp_per_capita * population))
    if gdp_per_capita is not None:
        indicators.append(_worldbank_fallback_indicator("NY.GDP.PCAP.CD", gdp_per_capita))
    if population is not None:
        indicators.append(_worldbank_fallback_indicator("SP.POP.TOTL", population))
    if internet_penetration is not None:
        indicators.append(_worldbank_fallback_indicator("IT.NET.USER.ZS", internet_penetration))
    return WorldBankCountryResponse(country_code=country_code, indicators=indicators, fallback_used=True)


def _worldbank_fallback_indicator(indicator_code: str, value: Decimal) -> WorldBankIndicatorItem:
    return WorldBankIndicatorItem(
        indicator_code=indicator_code,
        indicator_name=SUPPORTED_INDICATORS[indicator_code],
        year=2025,
        value=float(value),
        source=CSV_FALLBACK_SOURCE,
    )


def _fallback_gdelt_search(query: str, country: str | None, limit: int, seed_dir: Path) -> GdeltSearchResponse:
    rows = _ranked_content_rows(query, country, seed_dir, platforms={"GDELT Sample"})
    items = [
        GdeltArticleItem(
            title=row["title"],
            url=row["url"],
            domain=_domain_from_url(row.get("url")),
            published_at=row.get("published_at") or None,
            language="und",
            source=CSV_FALLBACK_SOURCE,
        )
        for row in rows[:limit]
        if row.get("title") and row.get("url")
    ]
    return GdeltSearchResponse(query=query, items=items, fallback_used=True)


def _fallback_youtube_search(keyword: str, country: str, limit: int, seed_dir: Path) -> YoutubeSearchResponse:
    from app.schemas import YoutubeVideoItem

    rows = _ranked_content_rows(keyword, country, seed_dir, platforms={"YouTube Sample"})
    items = [
        YoutubeVideoItem(
            country=(row.get("country") or country).upper(),
            keyword=row.get("keyword") or keyword,
            title=row["title"],
            channel_title=row.get("channel_or_community") or None,
            published_at=row.get("published_at") or None,
            thumbnail_url=None,
            video_url=row.get("url") or None,
            description=row.get("summary") or None,
            source_type=CSV_FALLBACK_SOURCE,
        )
        for row in rows[:limit]
        if row.get("title")
    ]
    return YoutubeSearchResponse(keyword=keyword, country=country, items=items, fallback_used=True)


def _competitor_response_from_etsy(response: EtsySearchResponse, limit: int) -> DataSourceCompetitorSearchResponse:
    items = [
        DataSourceCompetitorItem(
            platform=item.platform,
            country=item.country,
            keyword=item.keyword,
            title=item.title,
            price=item.price,
            currency=item.currency,
            image_url=item.image_url,
            product_url=item.product_url,
            category=item.category,
            rating=item.rating,
            review_count=item.review_count,
            source_type=item.source_type,
            collected_at=item.collected_at,
        )
        for item in response.items[:limit]
    ]
    return DataSourceCompetitorSearchResponse(
        keyword=response.keyword,
        country=response.country,
        items=items,
        fallback_used=False,
        sources=sorted({item.platform for item in items}),
    )


def _fallback_competitor_search(
    keyword: str,
    country: str,
    limit: int,
    seed_dir: Path,
) -> DataSourceCompetitorSearchResponse:
    rows = _ranked_competitor_rows(keyword, country, seed_dir)
    items = [
        DataSourceCompetitorItem(
            platform=row.get("platform") or "CSV Sample",
            country=(row.get("country") or country).upper(),
            keyword=row.get("keyword") or keyword,
            title=row["title"],
            price=_decimal_from_any(row.get("price")),
            currency=row.get("currency") or None,
            image_url=row.get("image_url") or None,
            product_url=row.get("product_url") or None,
            category=row.get("category") or None,
            rating=_decimal_from_any(row.get("rating")),
            review_count=_int_from_any(row.get("review_count")),
            source_type=CSV_FALLBACK_SOURCE,
            collected_at=_parse_datetime(row.get("collected_at")),
        )
        for row in rows[:limit]
        if row.get("title")
    ]
    return DataSourceCompetitorSearchResponse(
        keyword=keyword,
        country=country,
        items=items,
        fallback_used=True,
        sources=sorted({item.platform for item in items}),
    )


def _fallback_trade_data(
    product_category: str,
    hs_code: str,
    country: str,
    seed_dir: Path,
) -> UnComtradeTradeFlowResponse:
    partner = _trade_partner_code(country)
    rows = [
        row
        for row in _read_csv_rows(seed_dir / "trade_samples.csv")
        if _country_matches(row.get("reporter", ""), partner)
        and _country_matches(row.get("partner", ""), "CHN")
        and _flow_matches(row.get("flow", ""), "import")
        and _hs_matches(row.get("hs_code", ""), hs_code)
    ]
    grouped: dict[int, tuple[Decimal | None, Decimal | None]] = {}
    for row in rows:
        year = _int_from_any(row.get("year"))
        if year is None or year < DEFAULT_TRADE_START_YEAR or year > DEFAULT_TRADE_END_YEAR:
            continue
        trade_value, quantity = grouped.get(year, (None, None))
        grouped[year] = (
            _decimal_sum(trade_value, _decimal_from_any(row.get("trade_value_usd"))),
            _decimal_sum(quantity, _decimal_from_any(row.get("quantity"))),
        )
    records = [
        UnComtradeTradeRecord(
            year=year,
            trade_value_usd=values[0],
            quantity=values[1],
            source=CSV_FALLBACK_SOURCE,
        )
        for year, values in sorted(grouped.items())
    ]
    return UnComtradeTradeFlowResponse(
        hs_code=hs_code,
        reporter="CHN",
        partner=partner,
        flow="export",
        records=records,
        fallback_used=True,
        auth_mode="fallback",
    )


def _fallback_content_trend_items(
    keyword: str,
    country: str | None,
    limit: int,
    seed_dir: Path,
) -> list[DataSourceContentTrendItem]:
    rows = _ranked_content_rows(keyword, country, seed_dir, platforms=None)
    return [
        DataSourceContentTrendItem(
            platform=row.get("platform") or "CSV Sample",
            country=(row.get("country") or None),
            keyword=row.get("keyword") or keyword,
            title=row["title"],
            url=row.get("url") or None,
            channel_or_community=row.get("channel_or_community") or None,
            published_at=row.get("published_at") or None,
            heat_score=_decimal_from_any(row.get("heat_score")),
            summary=row.get("summary") or None,
            content_style=row.get("content_style") or None,
            source_type=CSV_FALLBACK_SOURCE,
        )
        for row in rows[:limit]
        if row.get("title")
    ]


def _ranked_content_rows(
    keyword: str,
    country: str | None,
    seed_dir: Path,
    *,
    platforms: set[str] | None,
) -> list[dict[str, str]]:
    rows = []
    normalized_keyword = _normalize_text(keyword)
    aliases = {normalized_keyword, *_keyword_aliases(normalized_keyword)}
    platform_keys = {platform.casefold() for platform in platforms} if platforms else None
    for row in _read_csv_rows(seed_dir / "content_trends.csv"):
        if platform_keys and row.get("platform", "").casefold() not in platform_keys:
            continue
        row_keyword = _normalize_text(row.get("keyword", ""))
        row_country = row.get("country", "").upper()
        keyword_match = row_keyword in aliases
        country_match = country is not None and row_country == country
        if keyword_match and country_match:
            rank = 0
        elif keyword_match:
            rank = 1
        elif country_match:
            rank = 2
        else:
            rank = 3
        rows.append(
            (
                rank,
                _decimal_from_any(row.get("heat_score")) or Decimal("0"),
                _parse_datetime(row.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
                row,
            )
        )
    rows.sort(key=lambda item: (item[0], -item[1], _reverse_datetime_key(item[2])))
    return [row for _rank, _heat, _published, row in rows]


def _ranked_competitor_rows(keyword: str, country: str, seed_dir: Path) -> list[dict[str, str]]:
    rows = []
    normalized_keyword = _normalize_text(keyword)
    aliases = {normalized_keyword, *_keyword_aliases(normalized_keyword)}
    seen_urls: set[str] = set()
    for row in _read_csv_rows(seed_dir / "competitor_samples.csv"):
        url = row.get("product_url", "")
        if url and url in seen_urls:
            continue
        row_keyword = _normalize_text(row.get("keyword", ""))
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
        rows.append(
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
    rows.sort(key=lambda item: (item[0], -item[1], -item[2], _reverse_datetime_key(item[3])))
    return [row for _rank, _rating, _reviews, _collected, row in rows]


def _dedupe_content_items(items: list[DataSourceContentTrendItem]) -> list[DataSourceContentTrendItem]:
    deduped: dict[str, DataSourceContentTrendItem] = {}
    for item in items:
        key = _content_dedupe_key(item)
        existing = deduped.get(key)
        if existing is None or _content_preferred(item, existing):
            deduped[key] = item
    return list(deduped.values())


def _content_dedupe_key(item: DataSourceContentTrendItem) -> str:
    if item.url:
        return f"url:{item.url.strip().lower()}"
    return f"text:{item.platform.casefold()}:{(item.country or '').upper()}:{_normalize_text(item.title)}"


def _content_preferred(left: DataSourceContentTrendItem, right: DataSourceContentTrendItem) -> bool:
    left_score = _source_priority(left.source_type)
    right_score = _source_priority(right.source_type)
    if left_score != right_score:
        return left_score < right_score
    left_heat = left.heat_score or Decimal("0")
    right_heat = right.heat_score or Decimal("0")
    if left_heat != right_heat:
        return left_heat > right_heat
    return (_parse_datetime(left.published_at) or datetime.min.replace(tzinfo=timezone.utc)) > (
        _parse_datetime(right.published_at) or datetime.min.replace(tzinfo=timezone.utc)
    )


def _content_sort_key(item: DataSourceContentTrendItem) -> tuple[int, Decimal, tuple[int, int, int, int, int, int, int]]:
    return (
        _source_priority(item.source_type),
        -(item.heat_score or Decimal("0")),
        _reverse_datetime_key(_parse_datetime(item.published_at) or datetime.min.replace(tzinfo=timezone.utc)),
    )


def _source_priority(source_type: str) -> int:
    return 0 if source_type == API_SOURCE else 1


def _keyword_aliases(keyword: str) -> tuple[str, ...]:
    aliases: dict[str, tuple[str, ...]] = {
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
        "pet products": ("pet cooling mat", "pet summer care"),
    }
    return aliases.get(keyword, ())


def _infer_hs_code(product_category: str) -> str:
    text = product_category.casefold()
    if any(marker in text for marker in ("towel", "bath", "kitchen linen")):
        return "630260"
    if any(marker in text for marker in ("blanket", "throw", "rug")):
        return "630140"
    if any(marker in text for marker in ("bedding", "duvet", "sheet", "pillowcase", "bed linen", "dorm")):
        return "630221"
    if any(marker in text for marker in ("cushion", "quilt", "pet mat", "swaddle", "pillow")):
        return "940490"
    return "6302"


def _response_source(response: BaseModel) -> str:
    if isinstance(response, DataSourceContentTrendResponse):
        return "mixed"
    if bool(getattr(response, "fallback_used", False)):
        return CSV_FALLBACK_SOURCE
    return API_SOURCE


def _safe_query_json(query: dict[str, object]) -> str:
    safe = json.dumps(redact_mapping(query), ensure_ascii=True, sort_keys=True, default=str)
    return safe[:1000]


def _safe_error_message(message: str | None) -> str | None:
    if not message:
        return None
    return redact_text("Provider failed or unavailable; CSV fallback used.")


def _find_row(path: Path, predicate: Callable[[dict[str, str]], bool]) -> dict[str, str] | None:
    for row in _read_csv_rows(path):
        if predicate(row):
            return row
    return None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [_clean_row(row) for row in csv.DictReader(csv_file) if not _is_blank_row(row)]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.strip().split()).lower()
    if not normalized:
        raise ValueError("Query text must not be empty")
    return normalized


def _normalize_country_key(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) not in {2, 3} or not normalized.isalpha():
        raise ValueError("Country must be a two- or three-letter code")
    return normalized


def _normalize_optional_country(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_country_key(value)


def _normalize_hs_code(value: str) -> str:
    normalized = value.strip().upper()
    if normalized == "TOTAL":
        return normalized
    if not normalized or not normalized.isdigit():
        raise ValueError("HS code must be numeric or TOTAL")
    return normalized


def _trade_partner_code(country: str) -> str:
    mapping = {
        "US": "USA",
        "USA": "USA",
        "GB": "GBR",
        "GBR": "GBR",
        "JP": "JPN",
        "JPN": "JPN",
        "AU": "AUS",
        "AUS": "AUS",
        "SG": "SGP",
        "SGP": "SGP",
        "CN": "CHN",
        "CHN": "CHN",
    }
    return mapping.get(country.upper(), country.upper())


def _country_matches(value: str, expected: str) -> bool:
    normalized = value.strip().upper()
    aliases = {
        "CHINA": "CHN",
        "CN": "CHN",
        "CHN": "CHN",
        "US": "USA",
        "USA": "USA",
        "UNITED STATES": "USA",
        "GB": "GBR",
        "GBR": "GBR",
        "UNITED KINGDOM": "GBR",
        "JP": "JPN",
        "JPN": "JPN",
        "JAPAN": "JPN",
        "AU": "AUS",
        "AUS": "AUS",
        "AUSTRALIA": "AUS",
        "SG": "SGP",
        "SGP": "SGP",
        "SINGAPORE": "SGP",
    }
    return aliases.get(normalized, normalized) == expected


def _flow_matches(value: str, expected: str) -> bool:
    return value.strip().casefold() in {expected.casefold(), expected[:1].casefold()}


def _hs_matches(value: str, requested_hs_code: str) -> bool:
    row_hs_code = value.strip().upper()
    if requested_hs_code == "TOTAL":
        return True
    if len(requested_hs_code) in {2, 4}:
        return row_hs_code.startswith(requested_hs_code)
    return row_hs_code == requested_hs_code


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


def _int_from_any(value: Any) -> int | None:
    parsed = _decimal_from_any(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (OverflowError, ValueError):
        return None


def _decimal_sum(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None:
        return right
    if right is None:
        return left
    return left + right


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


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    return urlparse(url).netloc or None


def _limit_youtube_response(response: YoutubeSearchResponse, limit: int) -> YoutubeSearchResponse:
    return YoutubeSearchResponse(
        keyword=response.keyword,
        country=response.country,
        items=response.items[:limit],
        fallback_used=response.fallback_used,
    )


def _limit_gdelt_response(response: GdeltSearchResponse, limit: int) -> GdeltSearchResponse:
    return GdeltSearchResponse(
        query=response.query,
        items=response.items[:limit],
        fallback_used=response.fallback_used,
    )


def _limit_competitor_response(
    response: DataSourceCompetitorSearchResponse,
    limit: int,
) -> DataSourceCompetitorSearchResponse:
    items = response.items[:limit]
    return DataSourceCompetitorSearchResponse(
        keyword=response.keyword,
        country=response.country,
        items=items,
        fallback_used=response.fallback_used,
        sources=sorted({item.platform for item in items}),
    )


def _limit_content_response(
    response: DataSourceContentTrendResponse,
    limit: int,
) -> DataSourceContentTrendResponse:
    items = response.items[:limit]
    return DataSourceContentTrendResponse(
        keyword=response.keyword,
        country=response.country,
        items=items,
        fallback_used=response.fallback_used,
        sources=sorted({item.platform for item in items}),
    )


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def _elapsed_ms(start: float) -> int:
    return max(0, round((perf_counter() - start) * 1000))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
