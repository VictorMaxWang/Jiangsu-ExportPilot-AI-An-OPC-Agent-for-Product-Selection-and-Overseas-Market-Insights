from __future__ import annotations

import csv
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.schemas import (
    AnalysisSource,
    MarketCompareResponse,
    MarketProfileAnalysisResponse,
    SuitableProductItem,
    UnComtradeTradeFlowResponse,
    WorldBankCountryResponse,
)
from app.services.ai import BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_market_profile_summary_messages
from app.services.ai.qwen_timeout import wait_for_qwen
from app.services.analysis_performance import mark_latest_qwen_fallback
from app.services.data_sources import DataSourceService
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
TARGET_COUNTRIES = ("US", "GB", "JP", "AU", "SG")
DEFAULT_MARKET_PROFILE_QWEN_TIMEOUT_SECONDS = 20.0

MARKET_LEVEL_SCORE = {"high": 85, "medium": 65, "low": 40}
LOGISTICS_SCORE = {"low": 90, "medium": 70, "high": 45}
COMPETITION_PENALTY = {"low": 0, "medium": 6, "high": 12, "unknown": 8}


class MarketProfileAnalysisService:
    def __init__(
        self,
        data_source_service: DataSourceService,
        *,
        ai_client: BailianClient | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._data_sources = data_source_service
        self._ai_client = ai_client or BailianClient()
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def analyze_country(
        self,
        country_code: str,
        product_category: str,
        *,
        keyword: str | None = None,
        hs_code: str | None = None,
        preloaded_signal: dict[str, Any] | None = None,
        use_ai_summary: bool = True,
    ) -> MarketProfileAnalysisResponse:
        normalized_country = _normalize_country(country_code)
        normalized_category = _normalize_text(product_category)
        normalized_keyword = _normalize_optional_text(keyword)
        normalized_hs_code = _normalize_hs_code(hs_code) if hs_code else _infer_hs_code(normalized_category)

        worldbank = _preloaded_response(preloaded_signal, "market", WorldBankCountryResponse)
        if worldbank is None:
            worldbank = await self._data_sources.get_market_profile(normalized_country)
        trade = _preloaded_response(preloaded_signal, "trade", UnComtradeTradeFlowResponse)
        if trade is None:
            trade = await self._data_sources.get_trade_data(
                normalized_category,
                hs_code=normalized_hs_code,
                country=normalized_country,
            )
        seed_profile = _market_profile_row(normalized_country, self._seed_dir) or {}

        scores = _score_market_profile(worldbank, trade, seed_profile, normalized_hs_code, self._seed_dir)
        competition_level = _competition_level(seed_profile)
        suitable_products = _suitable_products(
            normalized_country,
            normalized_category,
            normalized_keyword,
            normalized_hs_code,
            scores,
            competition_level,
            self._seed_dir,
        )
        evidence = _evidence_payload(worldbank, trade, seed_profile, scores)
        sources = _market_sources(worldbank, trade, seed_profile)

        if use_ai_summary:
            summary, ai_fallback_used = await self._summary(
                country_code=normalized_country,
                product_category=normalized_category,
                keyword=normalized_keyword,
                hs_code=normalized_hs_code,
                scores=scores,
                competition_level=competition_level,
                suitable_products=suitable_products,
                evidence=evidence,
                sources=sources,
            )
            sources.append(
                AnalysisSource(
                    provider="bailian",
                    source_label="qwen3.6-plus" if not ai_fallback_used else "AI fallback template",
                    source_type=API_SOURCE if not ai_fallback_used else "ai_fallback",
                    fallback_used=ai_fallback_used,
                    api_invoked=not ai_fallback_used,
                    detail="Generated market profile summary explanation.",
                )
            )
        else:
            summary = _fallback_summary(normalized_country, normalized_category, scores, competition_level, sources)
            ai_fallback_used = False
            sources.append(
                AnalysisSource(
                    provider="backend",
                    source_label="Local deterministic market profile summary",
                    source_type="local",
                    fallback_used=False,
                    api_invoked=False,
                    detail="Workflow summary built from DataCollectionAgent raw signals without Qwen.",
                )
            )

        return MarketProfileAnalysisResponse(
            country_code=normalized_country,
            country_name=seed_profile.get("country_name") or normalized_country,
            product_category=normalized_category,
            keyword=normalized_keyword,
            hs_code=normalized_hs_code,
            market_size_score=scores["market_size_score"],
            consumption_power_score=scores["consumption_power_score"],
            internet_score=scores["internet_score"],
            trade_score=scores["trade_score"],
            logistics_score=scores["logistics_score"],
            competition_level=competition_level,
            suitable_products=suitable_products,
            summary=summary,
            fallback_used=worldbank.fallback_used or trade.fallback_used,
            ai_fallback_used=ai_fallback_used,
            sources=_dedupe_sources(sources),
            evidence=evidence,
        )

    async def compare_markets(
        self,
        product_category: str,
        *,
        country_codes: list[str] | None = None,
        keyword: str | None = None,
        hs_code: str | None = None,
    ) -> MarketCompareResponse:
        countries = country_codes or list(TARGET_COUNTRIES)
        items = [
            await self.analyze_country(
                country,
                product_category,
                keyword=keyword,
                hs_code=hs_code,
            )
            for country in countries
        ]
        items.sort(key=_profile_sort_score, reverse=True)
        sources = _dedupe_sources([source for item in items for source in item.sources])
        return MarketCompareResponse(
            product_category=_normalize_text(product_category),
            keyword=_normalize_optional_text(keyword),
            hs_code=_normalize_hs_code(hs_code) if hs_code else _infer_hs_code(product_category),
            items=items,
            fallback_used=any(item.fallback_used for item in items),
            ai_fallback_used=any(item.ai_fallback_used for item in items),
            sources=sources,
        )

    async def _summary(
        self,
        *,
        country_code: str,
        product_category: str,
        keyword: str | None,
        hs_code: str,
        scores: dict[str, int],
        competition_level: str,
        suitable_products: list[SuitableProductItem],
        evidence: dict[str, Any],
        sources: list[AnalysisSource],
    ) -> tuple[str, bool]:
        payload = {
            "country_code": country_code,
            "product_category": product_category,
            "keyword": keyword,
            "hs_code": hs_code,
            "scores": scores,
            "competition_level": competition_level,
            "suitable_products": [item.model_dump(mode="json") for item in suitable_products[:5]],
            "evidence": evidence,
            "sources": [source.model_dump(mode="json") for source in sources],
        }
        try:
            result = await wait_for_qwen(
                self._ai_client.chat(
                    build_market_profile_summary_messages(payload),
                    temperature=0.3,
                    max_tokens=700,
                    json_mode=True,
                ),
                timeout_seconds=DEFAULT_MARKET_PROFILE_QWEN_TIMEOUT_SECONDS,
            )
            parsed = parse_json_object(result.content)
            summary = parsed.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary.strip(), False
        except (BailianError, AiJsonParseError, ValueError, TypeError, TimeoutError):
            mark_latest_qwen_fallback("market_profile_summary")
            pass
        return _fallback_summary(country_code, product_category, scores, competition_level, sources), True


def _preloaded_response(
    signal: dict[str, Any] | None,
    key: str,
    response_model: type[Any],
) -> Any | None:
    if not isinstance(signal, dict):
        return None
    value = signal.get(key)
    if isinstance(value, response_model):
        return value
    if isinstance(value, dict):
        try:
            return response_model.model_validate(value)
        except (TypeError, ValueError):
            return None
    return None


def _score_market_profile(
    worldbank: WorldBankCountryResponse,
    trade: UnComtradeTradeFlowResponse,
    seed_profile: dict[str, str],
    hs_code: str,
    seed_dir: Path,
) -> dict[str, int]:
    population = _indicator_value(worldbank, "SP.POP.TOTL") or _decimal_from_any(seed_profile.get("population"))
    gdp_per_capita = _indicator_value(worldbank, "NY.GDP.PCAP.CD") or _decimal_from_any(
        seed_profile.get("gdp_per_capita")
    )
    gdp = _indicator_value(worldbank, "NY.GDP.MKTP.CD")
    if gdp is None and population is not None and gdp_per_capita is not None:
        gdp = population * gdp_per_capita

    internet = _indicator_value(worldbank, "IT.NET.USER.ZS") or _decimal_from_any(
        seed_profile.get("internet_penetration")
    )
    market_size_level = seed_profile.get("market_size_level", "").casefold()
    market_size_score = _round_score(
        0.45 * _log_range_score(gdp, Decimal("100000000000"), Decimal("30000000000000"))
        + 0.25 * _log_range_score(population, Decimal("5000000"), Decimal("350000000"))
        + 0.30 * MARKET_LEVEL_SCORE.get(market_size_level, 55)
    )

    consumption_power_score = _round_score(_linear_score(gdp_per_capita, Decimal("20000"), Decimal("85000"), 40, 95))
    internet_score = _round_score(_decimal_to_float(internet))
    trade_score = _trade_score(trade, hs_code, seed_dir)
    logistics_score = LOGISTICS_SCORE.get(seed_profile.get("logistics_difficulty", "").casefold(), 55)

    return {
        "market_size_score": market_size_score,
        "consumption_power_score": consumption_power_score,
        "internet_score": internet_score,
        "trade_score": trade_score,
        "logistics_score": logistics_score,
    }


def _trade_score(trade: UnComtradeTradeFlowResponse, hs_code: str, seed_dir: Path) -> int:
    records = sorted(
        [record for record in trade.records if record.trade_value_usd is not None],
        key=lambda record: record.year,
    )
    if not records:
        return 0
    latest_value = records[-1].trade_value_usd or Decimal("0")
    benchmark_min, benchmark_max = _seed_trade_benchmark(hs_code, seed_dir)
    value_score = _log_range_score(latest_value, benchmark_min, benchmark_max)
    growth_score = 50.0
    first_value = records[0].trade_value_usd or Decimal("0")
    years = max(records[-1].year - records[0].year, 1)
    if first_value > 0 and latest_value > 0:
        cagr = (float(latest_value / first_value) ** (1 / years)) - 1
        growth_score = _clamp(50 + cagr * 500, 0, 100)
    return _round_score(0.80 * value_score + 0.20 * growth_score)


def _suitable_products(
    country_code: str,
    product_category: str,
    keyword: str | None,
    hs_code: str,
    scores: dict[str, int],
    competition_level: str,
    seed_dir: Path,
) -> list[SuitableProductItem]:
    rows = _read_csv_rows(seed_dir / "product_catalog.csv")
    items: list[SuitableProductItem] = []
    query_text = " ".join(part for part in (product_category, keyword or "") if part)
    for row in rows:
        product_keywords = row.get("keywords", "")
        product_text = " ".join(
            [
                row.get("product_name_en", ""),
                row.get("category", ""),
                product_keywords,
                row.get("description", ""),
            ]
        )
        product_hs = _infer_hs_code(product_text)
        trade_fit = _seed_trade_score(country_code, product_hs, seed_dir)
        content_heat = _content_heat_score(country_code, product_keywords, seed_dir)
        match_boost = 8 if _text_overlaps(query_text, product_text) or _hs_matches(product_hs, hs_code) else 0
        fit_score = _round_score(
            0.45 * trade_fit
            + 0.30 * content_heat
            + 0.15 * scores["consumption_power_score"]
            + 0.10 * scores["logistics_score"]
            - COMPETITION_PENALTY.get(competition_level, 8)
            + match_boost
        )
        reason = _product_reason(row, country_code, product_hs, trade_fit, content_heat)
        items.append(
            SuitableProductItem(
                product_key=row.get("product_key") or "UNKNOWN",
                product_name_cn=row.get("product_name_cn") or "",
                product_name_en=row.get("product_name_en") or "",
                category=row.get("category") or "",
                hs_code=product_hs,
                fit_score=fit_score,
                reason=reason,
                evidence=[
                    f"HS {product_hs} trade fit score: {trade_fit}",
                    f"Content heat score: {content_heat}",
                    f"Country consumption power score: {scores['consumption_power_score']}",
                ],
            )
        )
    items.sort(key=lambda item: (item.fit_score, item.product_key), reverse=True)
    return items[:5]


def _market_sources(
    worldbank: WorldBankCountryResponse,
    trade: UnComtradeTradeFlowResponse,
    seed_profile: dict[str, str],
) -> list[AnalysisSource]:
    return [
        AnalysisSource(
            provider="worldbank",
            source_label="World Bank API" if not worldbank.fallback_used else "CSV fallback: market_profiles.csv",
            source_type=API_SOURCE if not worldbank.fallback_used else CSV_FALLBACK_SOURCE,
            fallback_used=worldbank.fallback_used,
            api_invoked=not worldbank.fallback_used,
            detail="Macroeconomic and internet indicators.",
        ),
        AnalysisSource(
            provider="un_comtrade",
            source_label="UN Comtrade API" if not trade.fallback_used else "CSV fallback: trade_samples.csv",
            source_type=API_SOURCE if not trade.fallback_used else CSV_FALLBACK_SOURCE,
            fallback_used=trade.fallback_used,
            api_invoked=not trade.fallback_used and trade.auth_mode != "fallback",
            detail=f"Trade flow auth_mode={trade.auth_mode}.",
        ),
        AnalysisSource(
            provider="csv_seed",
            source_label="CSV seed: market_profiles.csv",
            source_type=CSV_FALLBACK_SOURCE,
            fallback_used=False,
            api_invoked=False,
            detail="Country qualitative fields." if seed_profile else "No seed profile row found.",
        ),
        AnalysisSource(
            provider="csv_seed",
            source_label="CSV seed: product_catalog.csv",
            source_type=CSV_FALLBACK_SOURCE,
            fallback_used=False,
            api_invoked=False,
            detail="Suitable product candidates.",
        ),
    ]


def _evidence_payload(
    worldbank: WorldBankCountryResponse,
    trade: UnComtradeTradeFlowResponse,
    seed_profile: dict[str, str],
    scores: dict[str, int],
) -> dict[str, Any]:
    return {
        "worldbank_indicators": [item.model_dump(mode="json") for item in worldbank.indicators],
        "trade_records": [item.model_dump(mode="json") for item in trade.records],
        "market_profile_seed": seed_profile,
        "scores": scores,
    }


def _fallback_summary(
    country_code: str,
    product_category: str,
    scores: dict[str, int],
    competition_level: str,
    sources: list[AnalysisSource],
) -> str:
    source_note = "CSV fallback/sample data is included." if any(source.source_type != API_SOURCE for source in sources) else "API data is included."
    return (
        f"{country_code} shows a market profile for {product_category} with market size "
        f"{scores['market_size_score']}, consumption power {scores['consumption_power_score']}, "
        f"internet readiness {scores['internet_score']}, trade fit {scores['trade_score']}, "
        f"and logistics readiness {scores['logistics_score']}. Competition is assessed as "
        f"{competition_level}. {source_note} Treat this as directional evidence, not a profit forecast."
    )


def _market_profile_row(country_code: str, seed_dir: Path) -> dict[str, str] | None:
    for row in _read_csv_rows(seed_dir / "market_profiles.csv"):
        if row.get("country_code", "").upper() == country_code:
            return row
    return None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return [_clean_row(row) for row in csv.DictReader(csv_file) if not _blank_row(row)]
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {key.strip(): (value or "").strip() for key, value in row.items() if key is not None}


def _blank_row(row: dict[str, str | None]) -> bool:
    return all(value is None or value == "" for key, value in row.items() if key is not None)


def _normalize_country(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) not in {2, 3} or not normalized.isalpha():
        raise ValueError("Country must be a two- or three-letter code")
    return normalized


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.strip().split()).lower()
    if not normalized:
        raise ValueError("Product category must not be empty")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_text(value)


def _normalize_hs_code(value: str | None) -> str:
    if value is None:
        raise ValueError("HS code must not be empty")
    normalized = value.strip().upper()
    if normalized == "TOTAL":
        return normalized
    if not normalized or not normalized.isdigit():
        raise ValueError("HS code must be numeric or TOTAL")
    return normalized


def _indicator_value(response: WorldBankCountryResponse, indicator_code: str) -> Decimal | None:
    values = [
        (item.year, _decimal_from_any(item.value))
        for item in response.indicators
        if item.indicator_code == indicator_code and item.value is not None
    ]
    usable = [(year, value) for year, value in values if value is not None]
    if not usable:
        return None
    usable.sort(key=lambda item: item[0], reverse=True)
    return usable[0][1]


def _decimal_from_any(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_float(value: Decimal | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _linear_score(value: Decimal | None, minimum: Decimal, maximum: Decimal, low: float, high: float) -> float:
    if value is None:
        return 0.0
    ratio = (value - minimum) / (maximum - minimum)
    return _clamp(low + float(ratio) * (high - low), 0, 100)


def _log_range_score(value: Decimal | None, minimum: Decimal, maximum: Decimal) -> float:
    if value is None or value <= 0:
        return 0.0
    safe_value = _clamp(float(value), float(minimum), float(maximum))
    if minimum <= 0 or maximum <= minimum:
        return 0.0
    return _clamp((math.log(safe_value) - math.log(float(minimum))) / (math.log(float(maximum)) - math.log(float(minimum))) * 100, 0, 100)


def _round_score(value: float | int) -> int:
    return int(round(_clamp(float(value), 0, 100)))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _competition_level(seed_profile: dict[str, str]) -> str:
    value = seed_profile.get("competition_level", "").casefold()
    return value if value in {"low", "medium", "high"} else "unknown"


def _infer_hs_code(text: str) -> str:
    normalized = text.casefold()
    if any(marker in normalized for marker in ("towel", "bath", "kitchen linen")):
        return "630260"
    if any(marker in normalized for marker in ("blanket", "throw", "rug")):
        return "630140"
    if any(marker in normalized for marker in ("bedding", "duvet", "sheet", "pillowcase", "bed linen", "dorm")):
        return "630221"
    if any(marker in normalized for marker in ("cushion", "quilt", "pet mat", "swaddle", "pillow", "baby")):
        return "940490"
    return "6302"


def _seed_trade_benchmark(hs_code: str, seed_dir: Path) -> tuple[Decimal, Decimal]:
    latest_by_country: dict[str, Decimal] = {}
    for row in _read_csv_rows(seed_dir / "trade_samples.csv"):
        if not _hs_matches(row.get("hs_code", ""), hs_code):
            continue
        country = _country_alias(row.get("reporter", ""))
        value = _decimal_from_any(row.get("trade_value_usd"))
        year = _decimal_from_any(row.get("year"))
        if not country or value is None or year is None:
            continue
        key = f"{country}:{int(year)}"
        latest_by_country[key] = value
    values = list(latest_by_country.values())
    if not values:
        return Decimal("10000000"), Decimal("1500000000")
    return max(min(values), Decimal("1000000")), max(max(values), Decimal("10000000"))


def _seed_trade_score(country_code: str, hs_code: str, seed_dir: Path) -> int:
    records = []
    for row in _read_csv_rows(seed_dir / "trade_samples.csv"):
        if _country_alias(row.get("reporter", "")) != country_code or not _hs_matches(row.get("hs_code", ""), hs_code):
            continue
        year = _decimal_from_any(row.get("year"))
        value = _decimal_from_any(row.get("trade_value_usd"))
        if year is not None and value is not None:
            records.append((int(year), value))
    if not records:
        return 0
    records.sort(key=lambda item: item[0])
    min_value, max_value = _seed_trade_benchmark(hs_code, seed_dir)
    return _round_score(_log_range_score(records[-1][1], min_value, max_value))


def _content_heat_score(country_code: str, product_keywords: str, seed_dir: Path) -> int:
    keywords = {_normalize_keyword_part(value) for value in product_keywords.split(";") if value.strip()}
    heat_values: list[Decimal] = []
    for row in _read_csv_rows(seed_dir / "content_trends.csv"):
        if row.get("country", "").upper() != country_code:
            continue
        if _normalize_keyword_part(row.get("keyword", "")) not in keywords:
            continue
        heat = _decimal_from_any(row.get("heat_score"))
        if heat is not None:
            heat_values.append(heat)
    if not heat_values:
        return 35
    return _round_score(sum(float(value) for value in heat_values) / len(heat_values))


def _normalize_keyword_part(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _country_alias(value: str) -> str | None:
    normalized = value.strip().upper()
    aliases = {
        "US": "US",
        "USA": "US",
        "UNITED STATES": "US",
        "GB": "GB",
        "GBR": "GB",
        "UNITED KINGDOM": "GB",
        "JP": "JP",
        "JPN": "JP",
        "JAPAN": "JP",
        "AU": "AU",
        "AUS": "AU",
        "AUSTRALIA": "AU",
        "SG": "SG",
        "SGP": "SG",
        "SINGAPORE": "SG",
    }
    return aliases.get(normalized)


def _hs_matches(row_hs_code: str, requested_hs_code: str) -> bool:
    normalized = row_hs_code.strip().upper()
    requested = requested_hs_code.strip().upper()
    if requested == "TOTAL":
        return True
    if len(requested) in {2, 4}:
        return normalized.startswith(requested)
    if len(normalized) in {2, 4}:
        return requested.startswith(normalized)
    return normalized == requested


def _text_overlaps(left: str, right: str) -> bool:
    left_tokens = {token for token in _normalize_keyword_part(left).split() if len(token) > 2}
    right_tokens = {token for token in _normalize_keyword_part(right).split() if len(token) > 2}
    return bool(left_tokens & right_tokens)


def _product_reason(row: dict[str, str], country_code: str, hs_code: str, trade_fit: int, content_heat: int) -> str:
    name = row.get("product_name_en") or row.get("product_key") or "Product"
    return (
        f"{name} matches {country_code} with HS {hs_code}, trade fit {trade_fit}, "
        f"and content heat {content_heat} from sample trend signals."
    )


def _profile_sort_score(item: MarketProfileAnalysisResponse) -> float:
    return (
        item.market_size_score * 0.25
        + item.consumption_power_score * 0.20
        + item.internet_score * 0.15
        + item.trade_score * 0.25
        + item.logistics_score * 0.15
    )


def _dedupe_sources(sources: list[AnalysisSource]) -> list[AnalysisSource]:
    deduped: dict[tuple[str, str, str], AnalysisSource] = {}
    for source in sources:
        key = (source.provider, source.source_label, source.source_type)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = source
        else:
            existing.fallback_used = existing.fallback_used or source.fallback_used
            existing.api_invoked = existing.api_invoked or source.api_invoked
    return list(deduped.values())
