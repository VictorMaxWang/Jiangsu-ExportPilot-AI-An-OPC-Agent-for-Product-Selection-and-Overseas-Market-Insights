from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.countries import (
    CNY_TO_TARGET_CURRENCY,
    COUNTRY_CURRENCY,
    COUNTRY_LOGISTICS_BASE,
    DEFAULT_TARGET_COUNTRIES,
)
from app.models import AnalysisRun, Company, OpportunityScore, Product, ProductDraft, ProductKeyword
from app.schemas import (
    AnalysisSource,
    CompetitorAnalysisResult,
    DataSourceCompetitorSearchResponse,
    DataSourceContentTrendResponse,
    OpportunityExplanation,
    OpportunityScoreResult,
    ScoringResultsResponse,
    ScoringRunRequest,
    ScoringRunResponse,
    UnComtradeTradeFlowResponse,
    WorldBankCountryResponse,
)
from app.services.ai import BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_opportunity_explanation_messages
from app.services.ai.qwen_timeout import wait_for_qwen
from app.services.analysis import analyze_competitors
from app.services.analysis_performance import mark_latest_qwen_fallback
from app.services.data_sources import DataSourceService
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE
from app.services.target_market_catalog import TargetMarketCatalogError, TargetMarketCatalogService


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_DIR = PROJECT_ROOT / "data" / "seed"
TARGET_COUNTRIES = DEFAULT_TARGET_COUNTRIES
DEFAULT_SCORING_QWEN_TIMEOUT_SECONDS = 20.0

WEIGHTS = {
    "trend_score": Decimal("0.25"),
    "price_score": Decimal("0.20"),
    "market_score": Decimal("0.20"),
    "supply_score": Decimal("0.20"),
    "logistics_score": Decimal("0.10"),
    "content_score": Decimal("0.05"),
}

class OpportunityScoringService:
    def __init__(
        self,
        db: Session,
        data_source_service: DataSourceService,
        *,
        ai_client: BailianClient | None = None,
        seed_dir: Path | None = None,
    ) -> None:
        self._db = db
        self._data_sources = data_source_service
        self._ai_client = ai_client or BailianClient()
        self._catalog_service = TargetMarketCatalogService(db)
        self._seed_dir = seed_dir or DEFAULT_SEED_DIR

    async def run(self, request: ScoringRunRequest) -> ScoringRunResponse:
        request.target_countries = self._validated_countries(request.target_countries)
        company = self._db.get(Company, request.company_id)
        if company is None:
            raise ValueError("Company not found")

        products = self._products_for_request(request)
        if not products:
            raise ValueError("No products found for scoring")

        started_at = _utc_now()
        analysis_run = AnalysisRun(
            company_id=request.company_id,
            status="running",
            input_products=[_product_input_snapshot(product, self._db) for product in products],
            target_countries=request.target_countries,
            started_at=started_at,
        )
        self._db.add(analysis_run)
        self._db.commit()
        self._db.refresh(analysis_run)

        return await self.run_for_analysis(request, analysis_run=analysis_run, final_status="completed")

    async def run_for_analysis(
        self,
        request: ScoringRunRequest,
        *,
        analysis_run: AnalysisRun,
        final_status: str | None = "completed",
        raw_signals: dict[str, dict[str, Any]] | None = None,
        use_ai_explanations: bool = False,
    ) -> ScoringRunResponse:
        request.target_countries = self._validated_countries(request.target_countries)
        company = self._db.get(Company, request.company_id)
        if company is None:
            raise ValueError("Company not found")
        if analysis_run.company_id != request.company_id:
            raise ValueError("Analysis run company mismatch")

        products = self._products_for_request(request)
        if not products:
            raise ValueError("No products found for scoring")

        try:
            analysis_run.input_products = [_product_input_snapshot(product, self._db) for product in products]
            analysis_run.target_countries = request.target_countries
            if analysis_run.started_at is None:
                analysis_run.started_at = _utc_now()
            self._delete_existing_scores(analysis_run.id)

            pending_items: list[OpportunityScoreResult] = []
            for product in products:
                keyword = self._keyword_for_product(product)
                for country in request.target_countries:
                    pending_items.append(
                        await self._score_product_country(
                            analysis_id=analysis_run.id,
                            product=product,
                            keyword=keyword,
                            country=country,
                            competitor_limit=request.competitor_limit,
                            raw_signal=_raw_signal_for(raw_signals, product.id, country),
                            use_ai_explanations=use_ai_explanations,
                        )
                    )

            pending_items.sort(key=lambda item: (item.total_score, item.product_id, item.country), reverse=True)
            persisted_items = self._persist_ranked_items(pending_items)

            if final_status is not None:
                analysis_run.status = final_status
                analysis_run.finished_at = _utc_now()
                self._db.commit()

            sources = _dedupe_sources([source for item in persisted_items for source in item.sources])
            return ScoringRunResponse(
                analysis_id=analysis_run.id,
                company_id=analysis_run.company_id,
                status=analysis_run.status,
                item_count=len(persisted_items),
                items=persisted_items,
                fallback_used=any(item.fallback_used for item in persisted_items),
                ai_fallback_used=any(item.ai_fallback_used for item in persisted_items),
                sources=sources,
            )
        except Exception as exc:
            if final_status is not None:
                analysis_run.status = "failed"
                analysis_run.finished_at = _utc_now()
                analysis_run.error_message = "Scoring run failed."
                self._db.commit()
            raise exc

    def _validated_countries(self, country_codes: list[str]) -> list[str]:
        try:
            return self._catalog_service.validate_analysis_countries(country_codes)
        except TargetMarketCatalogError as exc:
            raise ValueError(str(exc)) from exc

    def results(self, analysis_id: int) -> ScoringResultsResponse | None:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            return None

        rows = list(
            self._db.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.analysis_id == analysis_id)
                .order_by(OpportunityScore.rank.asc(), OpportunityScore.total_score.desc())
            )
        )
        products = {
            product.id: product
            for product in self._db.scalars(
                select(Product).where(Product.id.in_({row.product_id for row in rows} or {-1}))
            )
        }
        items = [_result_from_row(row, products.get(row.product_id)) for row in rows]
        sources = _dedupe_sources([source for item in items for source in item.sources])
        return ScoringResultsResponse(
            analysis_id=analysis_run.id,
            company_id=analysis_run.company_id,
            status=analysis_run.status,
            input_products=analysis_run.input_products,
            target_countries=analysis_run.target_countries,
            started_at=analysis_run.started_at,
            finished_at=analysis_run.finished_at,
            error_message=analysis_run.error_message,
            item_count=len(items),
            items=items,
            fallback_used=any(item.fallback_used for item in items),
            ai_fallback_used=any(item.ai_fallback_used for item in items),
            sources=sources,
        )

    def _products_for_request(self, request: ScoringRunRequest) -> list[Product]:
        statement = select(Product).where(Product.company_id == request.company_id).order_by(Product.id)
        if request.product_ids is not None:
            if not request.product_ids:
                return []
            statement = statement.where(Product.id.in_(request.product_ids))
        return list(self._db.scalars(statement))

    def _keyword_for_product(self, product: Product) -> str:
        keyword = next(iter(self._keywords_for_product(product)), None)
        for candidate in (keyword, product.product_name_en, product.category, product.product_name_cn):
            normalized = _optional_text(candidate)
            if normalized:
                return normalized
        return f"product {product.id}"

    def _keywords_for_product(self, product: Product) -> list[str]:
        return _stored_keywords_for_product(self._db, product)

    async def _score_product_country(
        self,
        *,
        analysis_id: int,
        product: Product,
        keyword: str,
        country: str,
        competitor_limit: int,
        raw_signal: dict[str, Any] | None = None,
        use_ai_explanations: bool = False,
    ) -> OpportunityScoreResult:
        normalized_country = country.strip().upper()
        product_category = product.category or keyword
        hs_code = _infer_hs_code(" ".join([product_category, keyword, product.description or ""]))

        competitors = _signal_response(raw_signal, "competitors", DataSourceCompetitorSearchResponse)
        if competitors is None:
            competitors = await self._data_sources.search_competitors(keyword, country=normalized_country, limit=competitor_limit)
        content = _signal_response(raw_signal, "content", DataSourceContentTrendResponse)
        if content is None:
            content = await self._data_sources.get_content_trends(keyword, country=normalized_country, limit=30)
        worldbank = _signal_response(raw_signal, "market", WorldBankCountryResponse)
        if worldbank is None:
            worldbank = await self._data_sources.get_market_profile(normalized_country)
        trade = _signal_response(raw_signal, "trade", UnComtradeTradeFlowResponse)
        if trade is None:
            trade = await self._data_sources.get_trade_data(product_category, hs_code=hs_code, country=normalized_country)

        competitor_analysis = analyze_competitors(
            keyword=keyword,
            country=normalized_country,
            competitor_items=competitors.items,
        )
        intake_source = _intake_source_for_product(self._db, product)
        deterministic_risks: list[str] = []
        scores = {
            "trend_score": _score_trend(content),
            "price_score": _score_price(product, competitor_analysis, deterministic_risks),
            "market_score": _score_market(worldbank, trade),
            "supply_score": _score_supply(product, intake_source),
            "logistics_score": _score_logistics(product, normalized_country),
            "content_score": _score_content_fit(product, keyword, content),
        }
        total_score = _weighted_total(scores)
        fallback_used = competitors.fallback_used or content.fallback_used or worldbank.fallback_used or trade.fallback_used
        sources = _sources_for_score(
            competitors=competitors,
            content=content,
            worldbank=worldbank,
            trade=trade,
            ai_fallback_used=False,
            include_ai_source=False,
        )
        evidence = _evidence_payload(
            product=product,
            product_keywords=self._keywords_for_product(product),
            intake_source=intake_source,
            keyword=keyword,
            country=normalized_country,
            hs_code=hs_code,
            scores=scores,
            total_score=total_score,
            competitor_analysis=competitor_analysis,
            competitors=competitors,
            content=content,
            worldbank=worldbank,
            trade=trade,
            deterministic_risks=deterministic_risks,
        )
        if use_ai_explanations:
            explanation, ai_fallback_used = await self._explanation(
                product=product,
                keyword=keyword,
                country=normalized_country,
                scores=scores,
                total_score=total_score,
                competitor_analysis=competitor_analysis,
                evidence=evidence,
                sources=sources,
                deterministic_risks=deterministic_risks,
            )
            ai_invoked = not ai_fallback_used
        else:
            explanation = _fallback_explanation(
                product=product,
                keyword=keyword,
                country=normalized_country,
                scores=scores,
                total_score=total_score,
                competitor_analysis=competitor_analysis,
                deterministic_risks=deterministic_risks,
                sources=sources,
            )
            ai_fallback_used = False
            ai_invoked = False
        sources = _sources_for_score(
            competitors=competitors,
            content=content,
            worldbank=worldbank,
            trade=trade,
            ai_fallback_used=ai_fallback_used,
            ai_invoked=ai_invoked,
        )
        return OpportunityScoreResult(
            analysis_id=analysis_id,
            product_id=product.id,
            product_name_cn=product.product_name_cn,
            product_name_en=product.product_name_en,
            country=normalized_country,
            keyword=keyword,
            trend_score=scores["trend_score"],
            price_score=scores["price_score"],
            market_score=scores["market_score"],
            supply_score=scores["supply_score"],
            logistics_score=scores["logistics_score"],
            content_score=scores["content_score"],
            total_score=total_score,
            rank=1,
            reason=explanation.reason,
            risk=explanation.risk,
            next_action=explanation.next_action,
            competitor_analysis=competitor_analysis,
            fallback_used=fallback_used,
            ai_fallback_used=ai_fallback_used,
            sources=sources,
            evidence=evidence,
        )

    async def _explanation(
        self,
        *,
        product: Product,
        keyword: str,
        country: str,
        scores: dict[str, Decimal],
        total_score: Decimal,
        competitor_analysis: CompetitorAnalysisResult,
        evidence: dict[str, Any],
        sources: list[AnalysisSource],
        deterministic_risks: list[str],
    ) -> tuple[OpportunityExplanation, bool]:
        fallback = _fallback_explanation(
            product=product,
            keyword=keyword,
            country=country,
            scores=scores,
            total_score=total_score,
            competitor_analysis=competitor_analysis,
            deterministic_risks=deterministic_risks,
            sources=sources,
        )
        payload = {
            "product": _product_input_snapshot(product, self._db),
            "keyword": keyword,
            "country": country,
            "computed_scores": {key: str(value) for key, value in scores.items()} | {"total_score": str(total_score)},
            "competitor_analysis": competitor_analysis.model_dump(mode="json"),
            "evidence": evidence,
            "sources": [source.model_dump(mode="json") for source in sources],
            "deterministic_risks": deterministic_risks,
        }
        try:
            result = await wait_for_qwen(
                self._ai_client.chat(
                    build_opportunity_explanation_messages(payload),
                    temperature=0.3,
                    max_tokens=700,
                    json_mode=True,
                ),
                timeout_seconds=DEFAULT_SCORING_QWEN_TIMEOUT_SECONDS,
            )
            parsed = parse_json_object(result.content)
            explanation = OpportunityExplanation.model_validate(parsed)
            return _merge_deterministic_risks(explanation, deterministic_risks), False
        except (BailianError, AiJsonParseError, ValidationError, ValueError, TypeError, TimeoutError):
            mark_latest_qwen_fallback("opportunity_explanation")
            return fallback, True

    def _persist_ranked_items(self, items: list[OpportunityScoreResult]) -> list[OpportunityScoreResult]:
        persisted: list[OpportunityScoreResult] = []
        for rank, item in enumerate(items, start=1):
            item.rank = rank
            row = OpportunityScore(
                analysis_id=item.analysis_id,
                product_id=item.product_id,
                country=item.country,
                trend_score=item.trend_score,
                price_score=item.price_score,
                market_score=item.market_score,
                supply_score=item.supply_score,
                logistics_score=item.logistics_score,
                content_score=item.content_score,
                total_score=item.total_score,
                rank=item.rank,
                reason=item.reason,
                risk=item.risk,
                next_action=item.next_action,
                fallback_used=item.fallback_used,
                ai_fallback_used=item.ai_fallback_used,
                sources=[source.model_dump(mode="json") for source in item.sources],
                evidence=_jsonable(item.evidence),
                competitor_analysis=item.competitor_analysis.model_dump(mode="json"),
            )
            self._db.add(row)
            self._db.flush()
            item.id = row.id
            persisted.append(item)
        self._db.commit()
        return persisted

    def _delete_existing_scores(self, analysis_id: int) -> None:
        rows = list(
            self._db.scalars(
                select(OpportunityScore).where(OpportunityScore.analysis_id == analysis_id)
            )
        )
        for row in rows:
            self._db.delete(row)
        if rows:
            self._db.flush()


def _score_trend(content: DataSourceContentTrendResponse) -> Decimal:
    heat_values = [Decimal(str(item.heat_score)) for item in content.items if item.heat_score is not None]
    if heat_values:
        return _score(sum(heat_values, Decimal("0")) / Decimal(len(heat_values)))
    if content.items:
        return _score(45 + min(len(content.items), 20))
    return Decimal("25.00")


def _score_price(product: Product, competitor: CompetitorAnalysisResult, risks: list[str]) -> Decimal:
    median_price = competitor.median_price
    if median_price <= 0 or product.cost_price_cny is None or product.cost_price_cny <= 0:
        return Decimal("45.00")

    target_currency = competitor.currency or COUNTRY_CURRENCY.get(competitor.country, "USD")
    cost_in_market_currency = Decimal(product.cost_price_cny) * CNY_TO_TARGET_CURRENCY.get(target_currency, Decimal("0.14"))
    estimated_market_price = cost_in_market_currency * Decimal("2.40")
    ratio = estimated_market_price / median_price

    if ratio < Decimal("0.35"):
        risks.append("Estimated launch price is far below the competitor band; verify quality, packaging, and landed cost assumptions.")
        score = 58 + float(ratio) * 60
    elif ratio <= Decimal("0.85"):
        score = 82 + (0.85 - float(ratio)) * 12
    elif ratio <= Decimal("1.15"):
        score = 78 - (float(ratio) - 0.85) * 45
    else:
        score = 55 - min((float(ratio) - 1.15) * 50, 35)
    return _score(score)


def _score_market(worldbank: WorldBankCountryResponse, trade: UnComtradeTradeFlowResponse) -> Decimal:
    population = _indicator_value(worldbank, "SP.POP.TOTL")
    gdp_per_capita = _indicator_value(worldbank, "NY.GDP.PCAP.CD")
    internet = _indicator_value(worldbank, "IT.NET.USER.ZS")
    trade_score = _trade_score(trade)
    market_size = _log_range_score(population, Decimal("5000000"), Decimal("350000000"))
    consumption = _linear_score(gdp_per_capita, Decimal("15000"), Decimal("85000"), 35, 95)
    internet_score = _clamp(float(internet or Decimal("0")), 0, 100)
    return _score(0.25 * market_size + 0.30 * consumption + 0.20 * internet_score + 0.25 * float(trade_score))


def _score_supply(product: Product, intake_source: dict[str, Any] | None = None) -> Decimal:
    score = 55
    if product.cost_price_cny is not None and product.cost_price_cny > 0:
        score += 8 if product.cost_price_cny <= 120 else 3
    if _optional_text(product.material):
        score += 10
    if _optional_text(product.certification):
        score += 15
    if product.moq is not None:
        if product.moq <= 150:
            score += 10
        elif product.moq <= 300:
            score += 5
        elif product.moq > 800:
            score -= 8
    if _optional_text(product.description):
        score += 5
    if _has_domestic_reference_price(intake_source):
        score += 3
    return _score(score)


def _score_logistics(product: Product, country: str) -> Decimal:
    score = COUNTRY_LOGISTICS_BASE.get(country, 60)
    weight = Decimal(product.weight_kg or 0)
    if weight <= 0:
        score -= 5
    elif weight <= Decimal("0.5"):
        score += 10
    elif weight <= Decimal("1.0"):
        score += 5
    elif weight <= Decimal("2.0"):
        score -= 5
    elif weight <= Decimal("5.0"):
        score -= 15
    else:
        score -= 28

    volume = _package_volume_cm3(product.package_size)
    if volume is not None:
        if volume <= Decimal("3000"):
            score += 5
        elif volume <= Decimal("12000"):
            score += 0
        elif volume <= Decimal("50000"):
            score -= 10
        else:
            score -= 22
    return _score(score)


def _score_content_fit(product: Product, keyword: str, content: DataSourceContentTrendResponse) -> Decimal:
    product_terms = _terms(" ".join([keyword, product.product_name_en or "", product.category or "", product.description or ""]))
    matched_scores: list[Decimal] = []
    for item in content.items:
        item_text = " ".join([item.keyword, item.title, item.summary or "", item.content_style or ""])
        if product_terms & _terms(item_text):
            matched_scores.append(Decimal(str(item.heat_score)) if item.heat_score is not None else Decimal("58"))
    if matched_scores:
        return _score(sum(matched_scores, Decimal("0")) / Decimal(len(matched_scores)))
    if content.items:
        return Decimal("40.00")
    return Decimal("25.00")


def _weighted_total(scores: dict[str, Decimal]) -> Decimal:
    value = sum((scores[key] * weight for key, weight in WEIGHTS.items()), Decimal("0"))
    return _score(value)


def _sources_for_score(
    *,
    competitors: DataSourceCompetitorSearchResponse,
    content: DataSourceContentTrendResponse,
    worldbank: WorldBankCountryResponse,
    trade: UnComtradeTradeFlowResponse,
    ai_fallback_used: bool,
    ai_invoked: bool = True,
    include_ai_source: bool = True,
) -> list[AnalysisSource]:
    competitor_detail = "Orchestrates Etsy API and competitor_samples.csv fallback; no eBay API is called."
    sources = [
        AnalysisSource(
            provider="etsy",
            source_label="Etsy API" if not competitors.fallback_used else "CSV fallback: competitor_samples.csv",
            source_type=API_SOURCE if not competitors.fallback_used else CSV_FALLBACK_SOURCE,
            fallback_used=competitors.fallback_used,
            api_invoked=not competitors.fallback_used,
            detail=competitor_detail,
        ),
        AnalysisSource(
            provider="data_source_service",
            source_label="Unified trend data",
            source_type="mixed",
            fallback_used=content.fallback_used,
            api_invoked=any(item.source_type == API_SOURCE for item in content.items),
            detail="Combines YouTube, GDELT, and content_trends.csv rows.",
        ),
        AnalysisSource(
            provider="worldbank",
            source_label="World Bank API" if not worldbank.fallback_used else "CSV fallback: market_profiles.csv",
            source_type=API_SOURCE if not worldbank.fallback_used else CSV_FALLBACK_SOURCE,
            fallback_used=worldbank.fallback_used,
            api_invoked=not worldbank.fallback_used,
            detail="Macroeconomic indicators.",
        ),
        AnalysisSource(
            provider="un_comtrade",
            source_label="UN Comtrade API" if not trade.fallback_used else "CSV fallback: trade_samples.csv",
            source_type=API_SOURCE if not trade.fallback_used else CSV_FALLBACK_SOURCE,
            fallback_used=trade.fallback_used,
            api_invoked=not trade.fallback_used and trade.auth_mode != "fallback",
            detail=f"Trade flow auth_mode={trade.auth_mode}.",
        ),
    ]
    if include_ai_source:
        if ai_invoked or ai_fallback_used:
            sources.append(
                AnalysisSource(
                    provider="bailian",
                    source_label="qwen3.6-plus" if not ai_fallback_used else "AI fallback template",
                    source_type=API_SOURCE if not ai_fallback_used else "ai_fallback",
                    fallback_used=ai_fallback_used,
                    api_invoked=not ai_fallback_used,
                    detail="Generates reason, risk, and next action only.",
                )
            )
        else:
            sources.append(
                AnalysisSource(
                    provider="backend",
                    source_label="Local deterministic opportunity explanation",
                    source_type="local",
                    fallback_used=False,
                    api_invoked=False,
                    detail="Reason, risk, and next action generated from backend score evidence without Qwen.",
                )
            )
    return _dedupe_sources(sources)


def _evidence_payload(
    *,
    product: Product,
    product_keywords: list[str],
    intake_source: dict[str, Any] | None,
    keyword: str,
    country: str,
    hs_code: str,
    scores: dict[str, Decimal],
    total_score: Decimal,
    competitor_analysis: CompetitorAnalysisResult,
    competitors: DataSourceCompetitorSearchResponse,
    content: DataSourceContentTrendResponse,
    worldbank: WorldBankCountryResponse,
    trade: UnComtradeTradeFlowResponse,
    deterministic_risks: list[str],
) -> dict[str, Any]:
    return _jsonable(
        {
            "product": _product_input_snapshot(product),
            "product_keywords": product_keywords,
            "intake_source": intake_source,
            "keyword": keyword,
            "country": country,
            "hs_code": hs_code,
            "scores": {key: str(value) for key, value in scores.items()},
            "total_score": str(total_score),
            "competitor_analysis": competitor_analysis.model_dump(mode="json"),
            "competitor_sources": competitors.sources,
            "competitor_fallback_used": competitors.fallback_used,
            "content_sources": content.sources,
            "content_fallback_used": content.fallback_used,
            "worldbank_indicators": [item.model_dump(mode="json") for item in worldbank.indicators],
            "trade_records": [item.model_dump(mode="json") for item in trade.records],
            "trade_fallback_used": trade.fallback_used,
            "trade_auth_mode": trade.auth_mode,
            "deterministic_risks": deterministic_risks,
        }
    )


def _fallback_explanation(
    *,
    product: Product,
    keyword: str,
    country: str,
    scores: dict[str, Decimal],
    total_score: Decimal,
    competitor_analysis: CompetitorAnalysisResult,
    deterministic_risks: list[str],
    sources: list[AnalysisSource],
) -> OpportunityExplanation:
    top_dimensions = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:2]
    low_dimensions = sorted(scores.items(), key=lambda item: item[1])[:2]
    product_name = product.product_name_en or product.product_name_cn
    source_note = " Some evidence uses CSV fallback/sample data." if any(source.fallback_used for source in sources) else ""
    reason = (
        f"{product_name} in {country} scores {total_score} because "
        f"{_readable_dimension(top_dimensions[0][0])} is {top_dimensions[0][1]} and "
        f"{_readable_dimension(top_dimensions[1][0])} is {top_dimensions[1][1]}. "
        f"Competitor scan found {competitor_analysis.item_count} rows for {keyword} with "
        f"{competitor_analysis.competition_level} competition.{source_note}"
    )
    risk_parts = list(deterministic_risks)
    risk_parts.append(
        f"Weaker dimensions are {_readable_dimension(low_dimensions[0][0])} ({low_dimensions[0][1]}) and "
        f"{_readable_dimension(low_dimensions[1][0])} ({low_dimensions[1][1]})."
    )
    if competitor_analysis.competition_level == "high":
        risk_parts.append("Competition is high, so differentiation and review-building need extra attention.")
    if any(source.fallback_used for source in sources):
        risk_parts.append("Fallback or sample data limits confidence; validate with live source checks before committing spend.")
    return OpportunityExplanation(
        reason=reason,
        risk=" ".join(risk_parts),
        next_action="Validate the competitor price band with live Etsy evidence, then run a small-country launch test with localized content and landed-cost review.",
    )


def _merge_deterministic_risks(explanation: OpportunityExplanation, risks: list[str]) -> OpportunityExplanation:
    if not risks:
        return explanation
    merged = explanation.risk
    for risk in risks:
        if risk.casefold() not in merged.casefold():
            merged = f"{merged} {risk}"
    return OpportunityExplanation(reason=explanation.reason, risk=merged, next_action=explanation.next_action)


def _result_from_row(row: OpportunityScore, product: Product | None) -> OpportunityScoreResult:
    competitor = CompetitorAnalysisResult.model_validate(row.competitor_analysis or _empty_competitor(row.country))
    return OpportunityScoreResult(
        id=row.id,
        analysis_id=row.analysis_id,
        product_id=row.product_id,
        product_name_cn=product.product_name_cn if product else "",
        product_name_en=product.product_name_en if product else None,
        country=row.country,
        keyword=str((row.evidence or {}).get("keyword") or competitor.keyword),
        trend_score=_decimal_or_zero(row.trend_score),
        price_score=_decimal_or_zero(row.price_score),
        market_score=_decimal_or_zero(row.market_score),
        supply_score=_decimal_or_zero(row.supply_score),
        logistics_score=_decimal_or_zero(row.logistics_score),
        content_score=_decimal_or_zero(row.content_score),
        total_score=_decimal_or_zero(row.total_score),
        rank=row.rank or 1,
        reason=row.reason or "",
        risk=row.risk or "",
        next_action=row.next_action or "",
        competitor_analysis=competitor,
        fallback_used=row.fallback_used,
        ai_fallback_used=row.ai_fallback_used,
        sources=[AnalysisSource.model_validate(source) for source in (row.sources or [])],
        evidence=row.evidence or {},
    )


def _product_input_snapshot(product: Product, db: Session | None = None) -> dict[str, Any]:
    return _jsonable(
        {
            "id": product.id,
            "product_name_cn": product.product_name_cn,
            "product_name_en": product.product_name_en,
            "category": product.category,
            "cost_price_cny": product.cost_price_cny,
            "weight_kg": product.weight_kg,
            "package_size": product.package_size,
            "material": product.material,
            "certification": product.certification,
            "moq": product.moq,
            "description": product.description,
            "product_keywords": _stored_keywords_for_product(db, product) if db is not None else [],
            "intake_source": _intake_source_for_product(db, product) if db is not None else None,
        }
    )


def _stored_keywords_for_product(db: Session, product: Product, *, limit: int = 10) -> list[str]:
    rows = list(
        db.scalars(
            select(ProductKeyword.keyword)
            .where(ProductKeyword.product_id == product.id)
            .order_by(ProductKeyword.id)
            .limit(limit)
        )
    )
    cleaned: list[str] = []
    seen: set[str] = set()
    for row in rows:
        keyword = _optional_text(row)
        if not keyword:
            continue
        key = keyword.casefold()
        if key in seen:
            continue
        cleaned.append(keyword)
        seen.add(key)
    return cleaned


def _intake_source_for_product(db: Session, product: Product) -> dict[str, Any] | None:
    draft = db.scalar(
        select(ProductDraft)
        .where(ProductDraft.confirmed_product_id == product.id)
        .order_by(ProductDraft.updated_at.desc(), ProductDraft.id.desc())
        .limit(1)
    )
    if draft is None:
        return None
    confidence_score = draft.confidence_score
    return _jsonable(
        {
            "confirmed_draft_id": draft.id,
            "import_job_id": draft.import_job_id,
            "source_type": draft.import_job.source_type if draft.import_job is not None else None,
            "source_platform": draft.source_platform,
            "source_url": _safe_url(draft.source_url),
            "evidence": draft.evidence or [],
            "confidence_score": confidence_score,
            "low_confidence": confidence_score is None or Decimal(str(confidence_score)) < Decimal("0.65"),
            "confirmation_note": "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。",
            "domestic_reference_price_cny": draft.price_cny,
            "domestic_price_role": "domestic_reference_only",
            "pricing_boundary_note": (
                "国内商品截图/链接价格仅用于判断产品信息完整度，不作为海外竞品价格、海外销售价格或采购成本。"
            ),
        }
    )


def _safe_url(value: str | None) -> str | None:
    text = _optional_text(value)
    if not text:
        return None
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return text[:300]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))[:300]


def _has_domestic_reference_price(intake_source: dict[str, Any] | None) -> bool:
    if not isinstance(intake_source, dict):
        return False
    platform = _optional_text(intake_source.get("source_platform")) or ""
    if platform.casefold() not in {"taobao", "tmall", "pinduoduo", "jd"}:
        return False
    value = intake_source.get("domestic_reference_price_cny")
    if value in (None, ""):
        return False
    try:
        return Decimal(str(value)) > 0
    except Exception:
        return False


def _indicator_value(response: WorldBankCountryResponse, indicator_code: str) -> Decimal | None:
    values = [
        (item.year, Decimal(str(item.value)))
        for item in response.indicators
        if item.indicator_code == indicator_code and item.value is not None
    ]
    if not values:
        return None
    values.sort(key=lambda item: item[0], reverse=True)
    return values[0][1]


def _trade_score(trade: UnComtradeTradeFlowResponse) -> Decimal:
    records = sorted([record for record in trade.records if record.trade_value_usd is not None], key=lambda item: item.year)
    if not records:
        return Decimal("0.00")
    latest = Decimal(records[-1].trade_value_usd or 0)
    value_score = _log_range_score(latest, Decimal("10000000"), Decimal("2000000000"))
    first = Decimal(records[0].trade_value_usd or 0)
    years = max(records[-1].year - records[0].year, 1)
    growth_score = 50.0
    if first > 0 and latest > 0:
        cagr = (float(latest / first) ** (1 / years)) - 1
        growth_score = _clamp(50 + cagr * 500, 0, 100)
    return _score(0.75 * value_score + 0.25 * growth_score)


def _linear_score(value: Decimal | None, minimum: Decimal, maximum: Decimal, low: float, high: float) -> float:
    if value is None:
        return 0.0
    ratio = (value - minimum) / (maximum - minimum)
    return _clamp(low + float(ratio) * (high - low), 0, 100)


def _log_range_score(value: Decimal | None, minimum: Decimal, maximum: Decimal) -> float:
    if value is None or value <= 0 or minimum <= 0 or maximum <= minimum:
        return 0.0
    safe_value = _clamp(float(value), float(minimum), float(maximum))
    return _clamp((math.log(safe_value) - math.log(float(minimum))) / (math.log(float(maximum)) - math.log(float(minimum))) * 100, 0, 100)


def _package_volume_cm3(package_size: str | None) -> Decimal | None:
    if not package_size:
        return None
    numbers = re.findall(r"\d+(?:\.\d+)?", package_size)
    if len(numbers) < 3:
        return None
    volume = Decimal("1")
    for number in numbers[:3]:
        volume *= Decimal(number)
    return volume


def _terms(text: str) -> set[str]:
    stop = {"and", "the", "for", "with", "from", "product", "sample", "fallback", "synthetic"}
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.casefold()) if token not in stop}


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


def _raw_signal_for(
    raw_signals: dict[str, dict[str, Any]] | None,
    product_id: int,
    country: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_signals, dict):
        return None
    signal = raw_signals.get(f"{product_id}:{country.strip().upper()}")
    return signal if isinstance(signal, dict) else None


def _signal_response(
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


def _readable_dimension(value: str) -> str:
    return value.replace("_", " ")


def _empty_competitor(country: str) -> dict[str, Any]:
    return {
        "keyword": "",
        "country": country,
        "item_count": 0,
        "min_price": "0.00",
        "median_price": "0.00",
        "max_price": "0.00",
        "avg_price": "0.00",
        "currency": COUNTRY_CURRENCY.get(country, ""),
        "common_terms": [],
        "competition_level": "low",
        "price_suggestion": "",
        "summary": "",
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_or_zero(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return _score(Decimal(str(value)))


def _score(value: Decimal | float | int) -> Decimal:
    return Decimal(str(_clamp(float(value), 0, 100))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
