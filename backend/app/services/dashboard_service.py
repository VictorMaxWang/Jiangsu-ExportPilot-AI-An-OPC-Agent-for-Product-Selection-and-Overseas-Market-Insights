from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, OpportunityScore, Product
from app.schemas import (
    DashboardContentTheme,
    DashboardCountryScore,
    DashboardDataSourceUsed,
    DashboardPriceRange,
    DashboardProductScore,
    DashboardRecommendation,
    DashboardResponse,
    DashboardRiskCard,
)


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_dashboard(self, analysis_id: int) -> DashboardResponse | None:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            return None

        score_rows = self._score_rows(analysis_id)
        products = self._products_by_id(score_rows)
        product_snapshots = _product_snapshots_by_id(analysis_run.input_products or [])
        state = dict(analysis_run.workflow_state or {})

        product_scores = [
            _product_score(row, products.get(row.product_id), product_snapshots.get(row.product_id))
            for row in score_rows
        ]
        return DashboardResponse(
            analysis_id=analysis_run.id,
            product_scores=product_scores,
            country_scores=_country_scores(product_scores),
            price_ranges=[
                _price_range(row, products.get(row.product_id), product_snapshots.get(row.product_id))
                for row in score_rows
                if row.competitor_analysis
            ],
            content_themes=_content_themes(state),
            top_recommendations=[
                _recommendation(row, products.get(row.product_id), product_snapshots.get(row.product_id))
                for row in score_rows[:5]
            ],
            risk_cards=_risk_cards(score_rows, products, product_snapshots),
            data_sources_used=_data_sources_used(analysis_run, score_rows, state),
        )

    def _score_rows(self, analysis_id: int) -> list[OpportunityScore]:
        return list(
            self._db.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.analysis_id == analysis_id)
                .order_by(OpportunityScore.rank.asc(), OpportunityScore.total_score.desc())
            )
        )

    def _products_by_id(self, rows: list[OpportunityScore]) -> dict[int, Product]:
        product_ids = {row.product_id for row in rows}
        if not product_ids:
            return {}
        return {
            product.id: product
            for product in self._db.scalars(select(Product).where(Product.id.in_(product_ids)))
        }


def _product_score(
    row: OpportunityScore,
    product: Product | None,
    snapshot: dict[str, Any] | None,
) -> DashboardProductScore:
    return DashboardProductScore(
        product_id=row.product_id,
        product_name_cn=_product_name_cn(product, snapshot),
        product_name_en=_product_name_en(product, snapshot),
        country=row.country,
        keyword=_keyword(row),
        rank=row.rank,
        total_score=_optional_decimal(row.total_score),
        trend_score=_optional_decimal(row.trend_score),
        price_score=_optional_decimal(row.price_score),
        market_score=_optional_decimal(row.market_score),
        supply_score=_optional_decimal(row.supply_score),
        logistics_score=_optional_decimal(row.logistics_score),
        content_score=_optional_decimal(row.content_score),
        fallback_used=row.fallback_used,
        ai_fallback_used=row.ai_fallback_used,
    )


def _country_scores(product_scores: list[DashboardProductScore]) -> list[DashboardCountryScore]:
    grouped: dict[str, list[DashboardProductScore]] = defaultdict(list)
    for item in product_scores:
        grouped[item.country].append(item)

    country_scores: list[DashboardCountryScore] = []
    for country, items in grouped.items():
        values = [item.total_score for item in items if item.total_score is not None]
        top = max(items, key=lambda item: item.total_score or Decimal("-1"), default=None)
        country_scores.append(
            DashboardCountryScore(
                country=country,
                average_score=_average(values),
                top_score=top.total_score if top else None,
                recommendation_count=len(items),
                top_product_id=top.product_id if top else None,
                top_product_name=_display_product_name(top.product_name_cn, top.product_name_en) if top else None,
            )
        )
    return sorted(country_scores, key=lambda item: item.top_score or Decimal("-1"), reverse=True)


def _price_range(
    row: OpportunityScore,
    product: Product | None,
    snapshot: dict[str, Any] | None,
) -> DashboardPriceRange:
    competitor = row.competitor_analysis or {}
    fallback_used = bool(row.fallback_used or _source_fallback_used(row.sources or []))
    return DashboardPriceRange(
        product_id=row.product_id,
        product_name=_display_product_name(_product_name_cn(product, snapshot), _product_name_en(product, snapshot)),
        country=row.country,
        keyword=_optional_text(competitor.get("keyword")) or _keyword(row),
        min_price=_optional_decimal(competitor.get("min_price")),
        median_price=_optional_decimal(competitor.get("median_price")),
        avg_price=_optional_decimal(competitor.get("avg_price")),
        max_price=_optional_decimal(competitor.get("max_price")),
        currency=_optional_text(competitor.get("currency")),
        item_count=_optional_int(competitor.get("item_count")),
        competition_level=_competition_level(competitor.get("competition_level")),
        price_suggestion=_optional_text(competitor.get("price_suggestion")),
        sample_notice=(
            "平台竞品样本来自公开 API 或 CSV fallback，仅表示价格区间信号，不代表真实销量。"
            if fallback_used
            else "平台竞品样本仅表示价格区间信号，不代表真实销量。"
        ),
    )


def _content_themes(state: dict[str, Any]) -> list[DashboardContentTheme]:
    weighted: dict[str, dict[str, Any]] = {}
    for trend in state.get("content_trends") or []:
        if not isinstance(trend, dict):
            continue
        source_count = _optional_int(trend.get("source_item_count"))
        for theme in trend.get("content_themes") or []:
            theme_text = _optional_text(theme)
            if not theme_text:
                continue
            key = theme_text.casefold()
            item = weighted.setdefault(
                key,
                {
                    "theme": theme_text,
                    "weight": 0,
                    "product_id": _optional_int_or_none(trend.get("product_id")),
                    "country": _optional_text(trend.get("country")),
                    "keyword": _optional_text(trend.get("keyword")),
                    "source_item_count": 0,
                },
            )
            item["weight"] = int(item["weight"]) + 1
            item["source_item_count"] = int(item["source_item_count"]) + source_count
    return [
        DashboardContentTheme(**item)
        for item in sorted(weighted.values(), key=lambda value: (int(value["weight"]), str(value["theme"])), reverse=True)
    ]


def _recommendation(
    row: OpportunityScore,
    product: Product | None,
    snapshot: dict[str, Any] | None,
) -> DashboardRecommendation:
    product_name_cn = _product_name_cn(product, snapshot)
    product_name_en = _product_name_en(product, snapshot)
    return DashboardRecommendation(
        rank=row.rank,
        product_id=row.product_id,
        product_name=_display_product_name(product_name_cn, product_name_en),
        country=row.country,
        total_score=_optional_decimal(row.total_score),
        reason=_optional_text(row.reason),
        next_action=_optional_text(row.next_action),
        fallback_used=row.fallback_used,
        ai_fallback_used=row.ai_fallback_used,
    )


def _risk_cards(
    rows: list[OpportunityScore],
    products: dict[int, Product],
    product_snapshots: dict[int, dict[str, Any]],
) -> list[DashboardRiskCard]:
    cards: list[DashboardRiskCard] = []
    seen: set[tuple[str, int | None, str | None, str]] = set()
    for row in rows:
        product = products.get(row.product_id)
        snapshot = product_snapshots.get(row.product_id)
        product_name = _display_product_name(_product_name_cn(product, snapshot), _product_name_en(product, snapshot))
        competitor = row.competitor_analysis or {}
        score = _optional_decimal(row.total_score)
        severity = "high" if score is not None and score < Decimal("50") else "medium"

        risk_text = _optional_text(row.risk)
        if risk_text:
            _append_risk_card(
                cards,
                seen,
                DashboardRiskCard(
                    title="机会评分风险",
                    severity=severity,
                    product_id=row.product_id,
                    product_name=product_name,
                    country=row.country,
                    message=risk_text,
                    source="opportunity_score",
                ),
            )

        if _competition_level(competitor.get("competition_level")) == "high":
            _append_risk_card(
                cards,
                seen,
                DashboardRiskCard(
                    title="竞品竞争偏高",
                    severity="high",
                    product_id=row.product_id,
                    product_name=product_name,
                    country=row.country,
                    message="竞品样本显示竞争水平为 high，演示建议强调差异化、评价积累和价格带验证。",
                    source="competitor_analysis",
                ),
            )

        if row.fallback_used or row.ai_fallback_used:
            _append_risk_card(
                cards,
                seen,
                DashboardRiskCard(
                    title="样本与 fallback 限制",
                    severity="medium",
                    product_id=row.product_id,
                    product_name=product_name,
                    country=row.country,
                    message="本条结果包含公开 API、样本数据或 CSV fallback 信号，可用于 Demo 判断，不代表真实销量或已验证成交额。",
                    source="data_lineage",
                ),
            )
    return cards


def _append_risk_card(
    cards: list[DashboardRiskCard],
    seen: set[tuple[str, int | None, str | None, str]],
    card: DashboardRiskCard,
) -> None:
    key = (card.title, card.product_id, card.country, card.message)
    if key in seen:
        return
    seen.add(key)
    cards.append(card)


def _data_sources_used(
    analysis_run: AnalysisRun,
    rows: list[OpportunityScore],
    state: dict[str, Any],
) -> list[DashboardDataSourceUsed]:
    sources: list[dict[str, Any]] = []
    for row in rows:
        sources.extend([source for source in (row.sources or []) if isinstance(source, dict)])
    sources.extend([source for source in state.get("provider_sources") or [] if isinstance(source, dict)])
    for log in analysis_run.step_logs or []:
        if isinstance(log, dict):
            sources.extend([source for source in log.get("sources") or [] if isinstance(source, dict)])
    for breakdown in state.get("provider_breakdown") or []:
        if isinstance(breakdown, dict):
            sources.extend(_sources_from_breakdown(breakdown))

    deduped: dict[tuple[str, str, str], DashboardDataSourceUsed] = {}
    for source in sources:
        provider = _optional_text(source.get("provider"))
        if not provider:
            continue
        label = _optional_text(source.get("source_label")) or _optional_text(source.get("label")) or provider
        source_type = _optional_text(source.get("source_type")) or "unknown"
        key = (provider, label, source_type)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = DashboardDataSourceUsed(
                provider=provider,
                label=label,
                source_type=source_type,
                fallback_used=bool(source.get("fallback_used")),
                api_invoked=bool(source.get("api_invoked")),
                detail=_optional_text(source.get("detail")),
            )
        else:
            existing.fallback_used = existing.fallback_used or bool(source.get("fallback_used"))
            existing.api_invoked = existing.api_invoked or bool(source.get("api_invoked"))
            existing.detail = existing.detail or _optional_text(source.get("detail"))
    return sorted(deduped.values(), key=lambda item: (item.provider, item.label, item.source_type))


def _sources_from_breakdown(breakdown: dict[str, Any]) -> list[dict[str, Any]]:
    provider = _optional_text(breakdown.get("provider"))
    if not provider:
        return []
    labels = [str(label) for label in breakdown.get("labels") or [] if _optional_text(label)]
    source_types = [str(source_type) for source_type in breakdown.get("source_types") or [] if _optional_text(source_type)]
    if not labels:
        labels = [provider]
    if not source_types:
        source_types = ["unknown"]
    return [
        {
            "provider": provider,
            "source_label": label,
            "source_type": source_type,
            "fallback_used": bool(breakdown.get("fallback_used")),
            "api_invoked": bool(breakdown.get("api_invoked")),
            "detail": "Aggregated provider summary from the analysis workflow.",
        }
        for label in labels
        for source_type in source_types
    ]


def _product_snapshots_by_id(values: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        product_id = _optional_int_or_none(item.get("id"))
        if product_id is not None:
            snapshots[product_id] = item
    return snapshots


def _product_name_cn(product: Product | None, snapshot: dict[str, Any] | None) -> str:
    if product is not None:
        return product.product_name_cn
    return _optional_text((snapshot or {}).get("product_name_cn")) or ""


def _product_name_en(product: Product | None, snapshot: dict[str, Any] | None) -> str | None:
    if product is not None:
        return product.product_name_en
    return _optional_text((snapshot or {}).get("product_name_en"))


def _display_product_name(product_name_cn: str, product_name_en: str | None) -> str:
    if product_name_en:
        return f"{product_name_cn} / {product_name_en}" if product_name_cn else product_name_en
    return product_name_cn or "未命名产品"


def _keyword(row: OpportunityScore) -> str | None:
    evidence = row.evidence or {}
    competitor = row.competitor_analysis or {}
    return _optional_text(evidence.get("keyword")) or _optional_text(competitor.get("keyword"))


def _source_fallback_used(sources: list[dict[str, Any]]) -> bool:
    return any(bool(source.get("fallback_used")) for source in sources if isinstance(source, dict))


def _competition_level(value: object) -> str:
    text = _optional_text(value)
    return text if text in {"low", "medium", "high"} else "unknown"


def _average(values: list[Decimal | None]) -> Decimal | None:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return _money(sum(cleaned, Decimal("0")) / Decimal(len(cleaned)))


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return _money(Decimal(str(value)))
    except Exception:
        return None


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _optional_int(value: object) -> int:
    parsed = _optional_int_or_none(value)
    return parsed if parsed is not None else 0


def _optional_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
