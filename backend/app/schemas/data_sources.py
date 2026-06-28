from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ApiCallStatus = Literal["success", "fallback", "cache_hit", "error"]


class DataSourceMarketProfileRequest(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=3)


class DataSourceSearchTrendsRequest(BaseModel):
    query: str = Field(..., min_length=1)
    country: str | None = Field(default=None, min_length=2, max_length=3)
    limit: int = Field(default=20, ge=1, le=50)
    force_live: bool = False


class DataSourceSearchCompetitorsRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    country: str | None = Field(default=None, min_length=2, max_length=3)
    limit: int = Field(default=20, ge=1, le=50)
    force_live: bool = False


class DataSourceTradeDataRequest(BaseModel):
    product_category: str = Field(..., min_length=1)
    hs_code: str | None = Field(default=None, min_length=1, max_length=16)
    country: str | None = Field(default=None, min_length=2, max_length=3)
    force_live: bool = False


class DataSourceCompetitorItem(BaseModel):
    platform: str
    country: str
    keyword: str
    title: str
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    category: str | None = None
    rating: Decimal | None = None
    review_count: int | None = None
    source_type: str
    collected_at: datetime | None = None


class DataSourceCompetitorSearchResponse(BaseModel):
    provider: Literal["data_source_service"] = "data_source_service"
    source_provider: Literal["etsy"] = "etsy"
    keyword: str
    country: str
    items: list[DataSourceCompetitorItem]
    fallback_used: bool = False
    sources: list[str] = Field(default_factory=list)


class DataSourceContentTrendItem(BaseModel):
    platform: str
    country: str | None = None
    keyword: str
    title: str
    url: str | None = None
    channel_or_community: str | None = None
    published_at: str | None = None
    heat_score: Decimal | None = None
    summary: str | None = None
    content_style: str | None = None
    source_type: str


class DataSourceContentTrendResponse(BaseModel):
    provider: Literal["data_source_service"] = "data_source_service"
    keyword: str
    country: str | None = None
    items: list[DataSourceContentTrendItem]
    fallback_used: bool = False
    sources: list[str] = Field(default_factory=list)


class DataSourceCacheStatusItem(BaseModel):
    provider: str
    endpoint: str
    fresh_count: int
    expired_count: int
    latest_fetched_at: datetime | None = None
    latest_expires_at: datetime | None = None


class DataSourceCacheStatusResponse(BaseModel):
    items: list[DataSourceCacheStatusItem]


class DataSourceCacheClearResponse(BaseModel):
    cache_table: Literal["data_source_caches"] = "data_source_caches"
    provider: str | None = None
    cleared_count: int


class ApiCallLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    endpoint: str
    query: str
    status: ApiCallStatus
    response_time_ms: int
    fallback_used: bool
    error_message: str | None = None
    called_at: datetime


class ApiCallLogListResponse(BaseModel):
    items: list[ApiCallLogItem]
    total: int
