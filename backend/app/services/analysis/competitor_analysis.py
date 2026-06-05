from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Protocol

from app.core.countries import COUNTRY_CURRENCY
from app.schemas import CompetitorAnalysisResult


STOP_TERMS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "this",
    "that",
    "synthetic",
    "fallback",
    "sample",
    "etsy",
    "amazon",
    "ebay",
    "rakuten",
    "walmart",
    "shop",
    "listing",
    "product",
    "marketplace",
    "us",
    "gb",
    "jp",
    "au",
    "sg",
    "kr",
    "my",
    "ae",
    "de",
    "fr",
    "nl",
    "it",
    "ca",
    "mx",
    "br",
    "cl",
    "nz",
    "za",
    "eg",
    "usa",
    "uk",
}


class CompetitorItemLike(Protocol):
    platform: str
    country: str
    keyword: str
    title: str
    price: Decimal | None
    currency: str | None
    category: str | None
    rating: Decimal | None
    review_count: int | None
    source_type: str


def analyze_competitors(
    *,
    keyword: str,
    country: str,
    competitor_items: list[CompetitorItemLike],
) -> CompetitorAnalysisResult:
    normalized_keyword = _normalize_text(keyword)
    normalized_country = country.strip().upper()
    currency = _primary_currency(normalized_country, competitor_items)
    price_values = _prices_for_currency(competitor_items, currency)
    common_terms = _common_terms(competitor_items)
    competition_level = _competition_level(competitor_items)

    if price_values:
        min_price = price_values[0]
        max_price = price_values[-1]
        median_price = _median_decimal(price_values)
        avg_price = _money(sum(price_values, Decimal("0")) / Decimal(len(price_values)))
    else:
        min_price = median_price = max_price = avg_price = Decimal("0.00")

    return CompetitorAnalysisResult(
        keyword=normalized_keyword,
        country=normalized_country,
        item_count=len(competitor_items),
        min_price=min_price,
        median_price=median_price,
        max_price=max_price,
        avg_price=avg_price,
        currency=currency,
        common_terms=common_terms,
        competition_level=competition_level,
        price_suggestion=_price_suggestion(currency, price_values),
        summary=_summary(
            keyword=normalized_keyword,
            country=normalized_country,
            item_count=len(competitor_items),
            currency=currency,
            median_price=median_price,
            competition_level=competition_level,
            common_terms=common_terms,
            fallback_used=any(item.source_type != "api" for item in competitor_items),
            platforms=sorted({item.platform for item in competitor_items}),
        ),
    )


def _primary_currency(country: str, items: list[CompetitorItemLike]) -> str:
    expected = COUNTRY_CURRENCY.get(country, "")
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        if item.price is None or not item.currency:
            continue
        counts[item.currency.upper()] += 1
    if expected and expected in counts:
        return expected
    if counts:
        return max(counts.items(), key=lambda pair: (pair[1], pair[0]))[0]
    return expected


def _prices_for_currency(items: list[CompetitorItemLike], currency: str) -> list[Decimal]:
    prices = [
        _money(item.price)
        for item in items
        if item.price is not None and (not currency or (item.currency or "").upper() == currency)
    ]
    prices = [price for price in prices if price > 0]
    prices.sort()
    return prices


def _common_terms(items: list[CompetitorItemLike]) -> list[str]:
    terms: list[str] = []
    for item in items:
        text = " ".join(part for part in (item.title, item.keyword, item.category or "") if part)
        terms.extend(_tokens(text))
    return [term for term, _count in Counter(terms).most_common(8)]


def _tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.casefold())
    return [token for token in tokens if token not in STOP_TERMS and not token.isdigit()]


def _competition_level(items: list[CompetitorItemLike]) -> str:
    item_count = len(items)
    platform_count = len({item.platform.casefold() for item in items})
    review_counts = sorted(item.review_count or 0 for item in items)
    median_reviews = median(review_counts) if review_counts else 0
    total_reviews = sum(review_counts)

    if item_count >= 25 or (platform_count >= 4 and median_reviews >= 120) or total_reviews >= 2500:
        return "high"
    if item_count >= 8 or platform_count >= 2 or median_reviews >= 40:
        return "medium"
    return "low"


def _price_suggestion(currency: str, prices: list[Decimal]) -> str:
    if not prices:
        return "No usable competitor price band was found; validate pricing with live marketplace data before launch."
    p25 = _percentile(prices, Decimal("0.25"))
    median_price = _median_decimal(prices)
    p75 = _percentile(prices, Decimal("0.75"))
    prefix = f"{currency} " if currency else ""
    return (
        f"Use {prefix}{p25}-{prefix}{median_price} for an entry test band and "
        f"{prefix}{median_price}-{prefix}{p75} for differentiated positioning."
    )


def _summary(
    *,
    keyword: str,
    country: str,
    item_count: int,
    currency: str,
    median_price: Decimal,
    competition_level: str,
    common_terms: list[str],
    fallback_used: bool,
    platforms: list[str],
) -> str:
    terms = ", ".join(common_terms[:5]) if common_terms else "no recurring terms"
    platform_note = ", ".join(platforms[:6]) if platforms else "no platform rows"
    data_note = " CSV fallback/sample data is included, so treat the signal as directional." if fallback_used else ""
    price_note = f" Median competitor price is {currency} {median_price}." if median_price > 0 else ""
    return (
        f"{country} competitor scan for {keyword} found {item_count} rows across {platform_note}. "
        f"Competition is {competition_level}; common terms include {terms}.{price_note}{data_note}"
    )


def _median_decimal(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.00")
    length = len(values)
    middle = length // 2
    if length % 2:
        return _money(values[middle])
    return _money((values[middle - 1] + values[middle]) / Decimal("2"))


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal:
    if not values:
        return Decimal("0.00")
    if len(values) == 1:
        return _money(values[0])
    rank = percentile * Decimal(len(values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    fraction = rank - Decimal(lower)
    return _money(values[lower] + (values[upper] - values[lower]) * fraction)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.strip().split()).lower()
    if not normalized:
        raise ValueError("Keyword must not be empty")
    return normalized
