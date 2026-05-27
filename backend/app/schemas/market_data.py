from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompetitorItemBase(BaseModel):
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
    seller_location: str | None = None
    source_type: str | None = None
    collected_at: datetime | None = None


class CompetitorItemCreate(CompetitorItemBase):
    pass


class CompetitorItemUpdate(BaseModel):
    platform: str | None = None
    country: str | None = None
    keyword: str | None = None
    title: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    category: str | None = None
    rating: Decimal | None = None
    review_count: int | None = None
    seller_location: str | None = None
    source_type: str | None = None
    collected_at: datetime | None = None


class CompetitorItemRead(CompetitorItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CompetitorItemListItem(CompetitorItemRead):
    pass


class MarketIndicatorBase(BaseModel):
    country_code: str
    country_name: str
    indicator_code: str
    indicator_name: str
    value: Decimal | None = None
    year: int
    source: str | None = None


class MarketIndicatorCreate(MarketIndicatorBase):
    pass


class MarketIndicatorUpdate(BaseModel):
    country_code: str | None = None
    country_name: str | None = None
    indicator_code: str | None = None
    indicator_name: str | None = None
    value: Decimal | None = None
    year: int | None = None
    source: str | None = None


class MarketIndicatorRead(MarketIndicatorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class MarketIndicatorListItem(MarketIndicatorRead):
    pass


class TradeStatBase(BaseModel):
    hs_code: str
    product_category: str | None = None
    reporter: str
    partner: str
    year: int
    flow: str
    trade_value_usd: Decimal | None = None
    quantity: Decimal | None = None
    source: str | None = None


class TradeStatCreate(TradeStatBase):
    pass


class TradeStatUpdate(BaseModel):
    hs_code: str | None = None
    product_category: str | None = None
    reporter: str | None = None
    partner: str | None = None
    year: int | None = None
    flow: str | None = None
    trade_value_usd: Decimal | None = None
    quantity: Decimal | None = None
    source: str | None = None


class TradeStatRead(TradeStatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class TradeStatListItem(TradeStatRead):
    pass


class NewsItemBase(BaseModel):
    source: str
    query: str
    country: str | None = None
    title: str
    url: str
    domain: str | None = None
    language: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    sentiment: str | None = None


class NewsItemCreate(NewsItemBase):
    pass


class NewsItemUpdate(BaseModel):
    source: str | None = None
    query: str | None = None
    country: str | None = None
    title: str | None = None
    url: str | None = None
    domain: str | None = None
    language: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    sentiment: str | None = None


class NewsItemRead(NewsItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class NewsItemListItem(NewsItemRead):
    pass


class ContentTrendBase(BaseModel):
    platform: str
    country: str | None = None
    keyword: str
    title: str
    url: str | None = None
    channel_or_community: str | None = None
    published_at: datetime | None = None
    heat_score: Decimal | None = None
    summary: str | None = None
    content_style: str | None = None


class ContentTrendCreate(ContentTrendBase):
    pass


class ContentTrendUpdate(BaseModel):
    platform: str | None = None
    country: str | None = None
    keyword: str | None = None
    title: str | None = None
    url: str | None = None
    channel_or_community: str | None = None
    published_at: datetime | None = None
    heat_score: Decimal | None = None
    summary: str | None = None
    content_style: str | None = None


class ContentTrendRead(ContentTrendBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ContentTrendListItem(ContentTrendRead):
    pass
