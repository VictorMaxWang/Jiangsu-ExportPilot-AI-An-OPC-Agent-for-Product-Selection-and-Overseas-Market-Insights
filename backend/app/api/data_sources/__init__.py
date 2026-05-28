from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ApiCallLog, DataSourceCache
from app.schemas import (
    ApiCallLogItem,
    ApiCallLogListResponse,
    DataSourceCacheStatusItem,
    DataSourceCacheStatusResponse,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendResponse,
    DataSourceMarketProfileRequest,
    DataSourceSearchCompetitorsRequest,
    DataSourceSearchTrendsRequest,
    DataSourceTradeDataRequest,
    UnComtradeTradeFlowResponse,
    WorldBankCountryResponse,
)
from app.services.data_sources import DataSourceService, get_data_source_service
from app.utils.redaction import redact_text


router = APIRouter()


@router.get("/cache-status", response_model=DataSourceCacheStatusResponse)
def get_cache_status(db: Session = Depends(get_db)) -> DataSourceCacheStatusResponse:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(DataSourceCache)).all()
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (row.provider, row.endpoint)
        item = grouped.setdefault(
            key,
            {
                "fresh_count": 0,
                "expired_count": 0,
                "latest_fetched_at": None,
                "latest_expires_at": None,
            },
        )
        expires_at = _as_aware(row.expires_at)
        fetched_at = _as_aware(row.fetched_at)
        if expires_at > now:
            item["fresh_count"] = int(item["fresh_count"]) + 1
        else:
            item["expired_count"] = int(item["expired_count"]) + 1
        if item["latest_fetched_at"] is None or fetched_at > item["latest_fetched_at"]:
            item["latest_fetched_at"] = fetched_at
        if item["latest_expires_at"] is None or expires_at > item["latest_expires_at"]:
            item["latest_expires_at"] = expires_at

    return DataSourceCacheStatusResponse(
        items=[
            DataSourceCacheStatusItem(
                provider=provider,
                endpoint=endpoint,
                fresh_count=int(values["fresh_count"]),
                expired_count=int(values["expired_count"]),
                latest_fetched_at=values["latest_fetched_at"],
                latest_expires_at=values["latest_expires_at"],
            )
            for (provider, endpoint), values in sorted(grouped.items())
        ]
    )


@router.get("/logs", response_model=ApiCallLogListResponse)
def get_api_call_logs(
    provider: str | None = Query(default=None, min_length=1),
    status_filter: str | None = Query(default=None, alias="status", min_length=1),
    fallback_used: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ApiCallLogListResponse:
    filters = []
    if provider:
        filters.append(ApiCallLog.provider == provider)
    if status_filter:
        filters.append(ApiCallLog.status == status_filter)
    if fallback_used is not None:
        filters.append(ApiCallLog.fallback_used == fallback_used)

    statement = select(ApiCallLog)
    count_statement = select(func.count()).select_from(ApiCallLog)
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)

    total = db.scalar(count_statement) or 0
    items = db.scalars(statement.order_by(ApiCallLog.called_at.desc(), ApiCallLog.id.desc()).offset(skip).limit(limit)).all()
    return ApiCallLogListResponse(
        items=[
            ApiCallLogItem(
                id=item.id,
                provider=item.provider,
                endpoint=item.endpoint,
                query=redact_text(item.query) or "",
                status=item.status,
                response_time_ms=item.response_time_ms,
                fallback_used=item.fallback_used,
                error_message=redact_text(item.error_message),
                called_at=item.called_at,
            )
            for item in items
        ],
        total=total,
    )


@router.post("/search-competitors", response_model=DataSourceCompetitorSearchResponse)
async def search_competitors(
    request: DataSourceSearchCompetitorsRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceCompetitorSearchResponse:
    try:
        return await service.search_competitors(
            request.keyword,
            country=request.country,
            limit=request.limit,
            force_live=request.force_live,
        )
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


@router.post("/search-trends", response_model=DataSourceContentTrendResponse)
async def search_trends(
    request: DataSourceSearchTrendsRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceContentTrendResponse:
    try:
        return await service.get_content_trends(
            request.query,
            country=request.country,
            limit=request.limit,
            force_live=request.force_live,
        )
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


@router.post("/market-profile", response_model=WorldBankCountryResponse)
async def get_market_profile(
    request: DataSourceMarketProfileRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> WorldBankCountryResponse:
    try:
        return await service.get_market_profile(request.country_code)
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


@router.post("/trade-data", response_model=UnComtradeTradeFlowResponse)
async def get_trade_data(
    request: DataSourceTradeDataRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> UnComtradeTradeFlowResponse:
    try:
        return await service.get_trade_data(
            request.product_category,
            hs_code=request.hs_code,
            country=request.country,
            force_live=request.force_live,
        )
    except ValueError as exc:
        raise _validation_exception(redact_text(str(exc)) or "") from exc


def _validation_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "code": "UNSUPPORTED_DATA_SOURCE_INPUT",
            "message": message,
        },
    )


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
