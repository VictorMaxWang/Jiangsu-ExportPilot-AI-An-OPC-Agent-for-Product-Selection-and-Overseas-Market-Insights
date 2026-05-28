from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CompetitorItem, ContentTrend, MarketIndicator, NewsItem, TradeStat
from app.schemas import (
    DataProviderSyncResponse,
    EtsySearchResponse,
    GdeltSearchResponse,
    UnComtradeTradeFlowResponse,
    WorldBankCountryResponse,
    YoutubeSearchResponse,
)
from app.services.providers import CSV_FALLBACK_SOURCE, DataProviderValidationError
from app.services.providers.etsy import EtsyProvider, etsy_seed_queries
from app.services.providers.gdelt import GdeltProvider, SUPPORTED_KEYWORDS
from app.services.providers.un_comtrade import UnComtradeProvider, un_comtrade_seed_queries
from app.services.providers.worldbank import SUPPORTED_COUNTRIES, WorldBankProvider
from app.services.providers.youtube import YoutubeProvider, youtube_seed_queries
from app.services.youtube_cache_service import YoutubeSearchCacheService
from app.utils.redaction import redact_text


router = APIRouter()


def get_worldbank_provider() -> WorldBankProvider:
    return WorldBankProvider()


def get_gdelt_provider() -> GdeltProvider:
    return GdeltProvider()


def get_youtube_provider() -> YoutubeProvider:
    return YoutubeProvider()


def get_etsy_provider() -> EtsyProvider:
    return EtsyProvider()


def get_un_comtrade_provider() -> UnComtradeProvider:
    return UnComtradeProvider()


def get_youtube_cache_service(
    db: Session = Depends(get_db),
    provider: YoutubeProvider = Depends(get_youtube_provider),
) -> YoutubeSearchCacheService:
    return YoutubeSearchCacheService(db, provider=provider)


@router.get("/worldbank/country/{country_code}", response_model=WorldBankCountryResponse)
async def get_worldbank_country(
    country_code: str,
    provider: WorldBankProvider = Depends(get_worldbank_provider),
) -> WorldBankCountryResponse:
    try:
        return await provider.fetch_country(country_code)
    except DataProviderValidationError as exc:
        raise _validation_exception("worldbank", redact_text(str(exc)) or "") from exc


@router.post("/worldbank/sync", response_model=DataProviderSyncResponse)
async def sync_worldbank(
    db: Session = Depends(get_db),
    provider: WorldBankProvider = Depends(get_worldbank_provider),
) -> DataProviderSyncResponse:
    inserted = 0
    updated = 0
    fallback_used = False
    errors: list[str] = []

    for country_code in SUPPORTED_COUNTRIES:
        try:
            payload = await provider.fetch_country(country_code)
        except DataProviderValidationError as exc:
            errors.append(redact_text(str(exc)) or "")
            continue

        fallback_used = fallback_used or payload.fallback_used
        for indicator in payload.indicators:
            existing = db.scalar(
                select(MarketIndicator).where(
                    MarketIndicator.country_code == payload.country_code,
                    MarketIndicator.indicator_code == indicator.indicator_code,
                    MarketIndicator.year == indicator.year,
                )
            )
            db_source = _worldbank_db_source(indicator.source)
            value = _decimal_from_number(indicator.value)
            if existing is None:
                db.add(
                    MarketIndicator(
                        country_code=payload.country_code,
                        country_name=SUPPORTED_COUNTRIES.get(payload.country_code, payload.country_code),
                        indicator_code=indicator.indicator_code,
                        indicator_name=indicator.indicator_name,
                        value=value,
                        year=indicator.year,
                        source=db_source,
                    )
                )
                inserted += 1
            else:
                existing.country_name = SUPPORTED_COUNTRIES.get(payload.country_code, payload.country_code)
                existing.indicator_name = indicator.indicator_name
                existing.value = value
                existing.source = db_source
                updated += 1

    _commit_or_500(db, "World Bank sync failed")
    return DataProviderSyncResponse(
        provider="worldbank",
        requested=len(SUPPORTED_COUNTRIES),
        inserted=inserted,
        updated=updated,
        fallback_used=fallback_used,
        errors=errors,
    )


@router.get("/gdelt/search", response_model=GdeltSearchResponse)
async def search_gdelt(
    query: str = Query(..., min_length=1),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    provider: GdeltProvider = Depends(get_gdelt_provider),
) -> GdeltSearchResponse:
    try:
        return await provider.search(query, country=country)
    except DataProviderValidationError as exc:
        raise _validation_exception("gdelt", redact_text(str(exc)) or "") from exc


@router.post("/gdelt/sync", response_model=DataProviderSyncResponse)
async def sync_gdelt(
    db: Session = Depends(get_db),
    provider: GdeltProvider = Depends(get_gdelt_provider),
) -> DataProviderSyncResponse:
    inserted = 0
    updated = 0
    skipped = 0
    fallback_used = False
    errors: list[str] = []

    for query in SUPPORTED_KEYWORDS:
        try:
            payload = await provider.search(query)
        except DataProviderValidationError as exc:
            errors.append(redact_text(str(exc)) or "")
            continue

        fallback_used = fallback_used or payload.fallback_used
        for item in payload.items:
            if not item.url:
                skipped += 1
                continue
            existing = db.scalar(
                select(NewsItem).where(
                    NewsItem.query == payload.query,
                    NewsItem.url == item.url,
                )
            )
            db_source = _gdelt_db_source(item.source)
            published_at = _parse_datetime(item.published_at)
            if existing is None:
                db.add(
                    NewsItem(
                        source=db_source,
                        query=payload.query,
                        country=None,
                        title=item.title,
                        url=item.url,
                        domain=item.domain,
                        language=item.language,
                        published_at=published_at,
                    )
                )
                inserted += 1
            else:
                existing.source = db_source
                existing.title = item.title
                existing.domain = item.domain
                existing.language = item.language
                existing.published_at = published_at
                updated += 1

    _commit_or_500(db, "GDELT sync failed")
    return DataProviderSyncResponse(
        provider="gdelt",
        requested=len(SUPPORTED_KEYWORDS),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        fallback_used=fallback_used,
        errors=errors,
    )


@router.get("/youtube/search", response_model=YoutubeSearchResponse)
async def search_youtube(
    keyword: str = Query(..., min_length=1),
    country: str = Query(default="US", min_length=2, max_length=2),
    limit: int = Query(default=10, ge=1, le=10),
    service: YoutubeSearchCacheService = Depends(get_youtube_cache_service),
) -> YoutubeSearchResponse:
    try:
        return await service.search_videos(keyword, country=country, limit=limit)
    except DataProviderValidationError as exc:
        raise _validation_exception("youtube", redact_text(str(exc)) or "") from exc


@router.post("/youtube/sync", response_model=DataProviderSyncResponse)
async def sync_youtube(
    db: Session = Depends(get_db),
    service: YoutubeSearchCacheService = Depends(get_youtube_cache_service),
) -> DataProviderSyncResponse:
    inserted = 0
    updated = 0
    skipped = 0
    fallback_used = False
    errors: list[str] = []
    queries = youtube_seed_queries()

    for keyword, country in queries:
        try:
            payload = await service.search_videos(keyword, country=country, limit=10)
        except DataProviderValidationError as exc:
            errors.append(redact_text(str(exc)) or "")
            continue

        fallback_used = fallback_used or payload.fallback_used
        for item in payload.items:
            if not item.video_url:
                skipped += 1
                continue
            existing = db.scalar(
                select(ContentTrend).where(
                    ContentTrend.platform == item.platform,
                    ContentTrend.country == item.country,
                    ContentTrend.keyword == item.keyword,
                    ContentTrend.url == item.video_url,
                )
            )
            published_at = _parse_datetime(item.published_at)
            if existing is None:
                db.add(
                    ContentTrend(
                        platform=item.platform,
                        country=item.country,
                        keyword=item.keyword,
                        title=item.title,
                        url=item.video_url,
                        channel_or_community=item.channel_title,
                        published_at=published_at,
                        heat_score=None,
                        summary=item.description,
                        content_style=item.source_type,
                    )
                )
                inserted += 1
            else:
                existing.title = item.title
                existing.channel_or_community = item.channel_title
                existing.published_at = published_at
                existing.summary = item.description
                existing.content_style = item.source_type
                updated += 1

    _commit_or_500(db, "YouTube sync failed")
    return DataProviderSyncResponse(
        provider="youtube",
        requested=len(queries),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        fallback_used=fallback_used,
        errors=errors,
    )


@router.get("/etsy/search", response_model=EtsySearchResponse)
async def search_etsy(
    keyword: str = Query(..., min_length=1),
    country: str = Query(default="US", min_length=1),
    limit: int = Query(default=20, ge=1, le=20),
    provider: EtsyProvider = Depends(get_etsy_provider),
) -> EtsySearchResponse:
    try:
        return await provider.search_listings(keyword, country=country, limit=limit)
    except DataProviderValidationError as exc:
        raise _validation_exception("etsy", redact_text(str(exc)) or "") from exc


@router.post("/etsy/sync", response_model=DataProviderSyncResponse)
async def sync_etsy(
    db: Session = Depends(get_db),
    provider: EtsyProvider = Depends(get_etsy_provider),
) -> DataProviderSyncResponse:
    inserted = 0
    updated = 0
    skipped = 0
    fallback_used = False
    errors: list[str] = []
    queries = etsy_seed_queries()

    for keyword, country in queries:
        try:
            payload = await provider.search_listings(keyword, country=country, limit=20)
        except DataProviderValidationError as exc:
            errors.append(redact_text(str(exc)) or "")
            continue

        fallback_used = fallback_used or payload.fallback_used
        for item in payload.items:
            if not item.product_url and not item.title:
                skipped += 1
                continue
            existing = _find_etsy_competitor(db, item)
            if existing is None:
                db.add(
                    CompetitorItem(
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
                )
                inserted += 1
            else:
                existing.title = item.title
                existing.price = item.price
                existing.currency = item.currency
                existing.image_url = item.image_url
                existing.product_url = item.product_url
                existing.category = item.category
                existing.rating = item.rating
                existing.review_count = item.review_count
                existing.source_type = item.source_type
                existing.collected_at = item.collected_at
                updated += 1

    _commit_or_500(db, "Etsy sync failed")
    return DataProviderSyncResponse(
        provider="etsy",
        requested=len(queries),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        fallback_used=fallback_used,
        errors=errors,
    )


@router.get("/comtrade/trade-flow", response_model=UnComtradeTradeFlowResponse)
async def get_un_comtrade_trade_flow(
    reporter: str = Query(default="CHN", min_length=2),
    partner: str = Query(default="USA", min_length=2),
    hs_code: str = Query(default="6302", min_length=1),
    flow: str = Query(default="export", min_length=1),
    start_year: int = Query(default=2020, ge=1900, le=2100),
    end_year: int = Query(default=2025, ge=1900, le=2100),
    provider: UnComtradeProvider = Depends(get_un_comtrade_provider),
) -> UnComtradeTradeFlowResponse:
    try:
        return await provider.get_trade_flow(
            reporter=reporter,
            partner=partner,
            hs_code=hs_code,
            flow=flow,
            start_year=start_year,
            end_year=end_year,
        )
    except DataProviderValidationError as exc:
        raise _validation_exception("un_comtrade", redact_text(str(exc)) or "") from exc


@router.post("/comtrade/sync", response_model=DataProviderSyncResponse)
async def sync_un_comtrade(
    db: Session = Depends(get_db),
    provider: UnComtradeProvider = Depends(get_un_comtrade_provider),
) -> DataProviderSyncResponse:
    inserted = 0
    updated = 0
    skipped = 0
    fallback_used = False
    errors: list[str] = []
    queries = un_comtrade_seed_queries()

    for query in queries:
        try:
            payload = await provider.get_trade_flow(
                reporter=query.reporter,
                partner=query.partner,
                hs_code=query.hs_code,
                flow=query.flow,
                start_year=query.start_year,
                end_year=query.end_year,
            )
        except DataProviderValidationError as exc:
            errors.append(redact_text(str(exc)) or "")
            continue

        fallback_used = fallback_used or payload.fallback_used
        if not payload.records:
            skipped += 1
            continue

        for record in payload.records:
            existing = db.scalar(
                select(TradeStat).where(
                    TradeStat.hs_code == payload.hs_code,
                    TradeStat.reporter == payload.reporter,
                    TradeStat.partner == payload.partner,
                    TradeStat.year == record.year,
                    TradeStat.flow == payload.flow,
                )
            )
            db_source = _un_comtrade_db_source(record.source, payload.auth_mode)
            if existing is None:
                db.add(
                    TradeStat(
                        hs_code=payload.hs_code,
                        product_category=None,
                        reporter=payload.reporter,
                        partner=payload.partner,
                        year=record.year,
                        flow=payload.flow,
                        trade_value_usd=record.trade_value_usd,
                        quantity=record.quantity,
                        source=db_source,
                    )
                )
                inserted += 1
            else:
                existing.trade_value_usd = record.trade_value_usd
                existing.quantity = record.quantity
                existing.source = db_source
                updated += 1

    _commit_or_500(db, "UN Comtrade sync failed")
    return DataProviderSyncResponse(
        provider="un_comtrade",
        requested=len(queries),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        fallback_used=fallback_used,
        errors=errors,
    )


def _validation_exception(provider: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "UNSUPPORTED_DATA_PROVIDER_INPUT",
            "message": message,
            "provider": provider,
        },
    )


def _worldbank_db_source(source: str) -> str:
    if source == CSV_FALLBACK_SOURCE:
        return "worldbank_csv_fallback"
    return "worldbank_api"


def _gdelt_db_source(source: str) -> str:
    if source == CSV_FALLBACK_SOURCE:
        return "gdelt_csv_fallback"
    return "gdelt_api"


def _un_comtrade_db_source(source: str, auth_mode: str) -> str:
    if source == CSV_FALLBACK_SOURCE:
        return "un_comtrade_csv_fallback"
    if auth_mode == "key":
        return "un_comtrade_api_key"
    return "un_comtrade_api_no_key"


def _find_etsy_competitor(db: Session, item: object) -> CompetitorItem | None:
    statement = select(CompetitorItem).where(
        CompetitorItem.platform == getattr(item, "platform"),
        CompetitorItem.country == getattr(item, "country"),
        CompetitorItem.keyword == getattr(item, "keyword"),
    )
    product_url = getattr(item, "product_url")
    if product_url:
        statement = statement.where(CompetitorItem.product_url == product_url)
    else:
        statement = statement.where(
            CompetitorItem.product_url.is_(None),
            CompetitorItem.title == getattr(item, "title"),
        )
    return db.scalar(statement)


def _decimal_from_number(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _commit_or_500(db: Session, message: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message) from exc
