from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import SessionLocal
from app.models import AnalysisRun, Company, OpportunityScore, Product, ProductDraft, ProductKeyword, Report
from app.schemas import (
    AnalysisDetailResponse,
    AnalysisRunRequest,
    AnalysisRunStartResponse,
    AnalysisStatusResponse,
    AnalysisStepLog,
    MarketingCopyResponse,
    ProductKeywordsRequest,
    ProviderBreakdownItem,
    ReportCreate,
    ReportSectionResponse,
    ScoringRunRequest,
    ScoringSummary,
)
from app.services import report_service
from app.services.ai import (
    AiStructuredOutputError,
    BailianClient,
    BailianError,
    generate_product_keywords,
)
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_marketing_copy_messages, build_report_section_messages
from app.services.analysis import ContentTrendAnalysisService, MarketProfileAnalysisService, analyze_competitors
from app.services.data_sources import DataSourceService
from app.services.providers import API_SOURCE, CSV_FALLBACK_SOURCE
from app.services.reports import ReportGenerationInputError, ReportGenerator
from app.services.scoring import OpportunityScoringService
from app.utils.redaction import redact_text


WORKFLOW_STATUS_WAITING = "waiting"
WORKFLOW_STATUS_RUNNING = "running"
WORKFLOW_STATUS_SUCCESS = "success"
WORKFLOW_STATUS_FAILED = "failed"
WORKFLOW_STATUS_FALLBACK_USED = "fallback_used"
NEXT_PAGE_URL_TEMPLATE = "/reports?analysis_id={analysis_id}"
OPTIONAL_PROVIDERS = {"ebay", "rakuten", "reddit"}


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    node: str
    title: str


WORKFLOW_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep("01_company_profiling", "CompanyProfilingAgent", "Company profiling"),
    WorkflowStep("02_product_understanding", "ProductUnderstandingAgent", "Product understanding"),
    WorkflowStep("03_data_collection", "DataCollectionAgent", "Data collection"),
    WorkflowStep("04_competitor_analysis", "CompetitorAnalysisAgent", "Competitor analysis"),
    WorkflowStep("05_market_profiling", "MarketProfilingAgent", "Market profiling"),
    WorkflowStep("06_content_trend", "ContentTrendAgent", "Content trend"),
    WorkflowStep("07_opportunity_scoring", "OpportunityScoringAgent", "Opportunity scoring"),
    WorkflowStep("08_marketing_prep", "MarketingPrepAgent", "Marketing prep"),
    WorkflowStep("09_report_prep", "ReportPrepAgent", "Report prep"),
)


class WorkflowInputError(ValueError):
    def __init__(self, message: str, *, code: str = "UNSUPPORTED_ANALYSIS_INPUT") -> None:
        self.code = code
        super().__init__(message)


@dataclass
class WorkflowContext:
    db: Session
    analysis_run: AnalysisRun
    request: AnalysisRunRequest
    data_sources: DataSourceService
    ai_client: BailianClient
    state: dict[str, Any]


@dataclass
class StepResult:
    output_summary: dict[str, Any]
    state_updates: dict[str, Any] | None = None
    sources: list[dict[str, Any]] | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


class ExportInsightWorkflow:
    def __init__(
        self,
        db: Session,
        data_source_service: DataSourceService,
        *,
        ai_client: BailianClient | None = None,
    ) -> None:
        self._db = db
        self._data_sources = data_source_service
        self._ai_client = ai_client or BailianClient()
        self._agents = [
            CompanyProfilingAgent(),
            ProductUnderstandingAgent(),
            DataCollectionAgent(),
            CompetitorAnalysisAgent(),
            MarketProfilingAgent(),
            ContentTrendAgent(),
            OpportunityScoringAgent(),
            MarketingPrepAgent(),
            ReportPrepAgent(),
        ]

    def create_run(self, request: AnalysisRunRequest) -> AnalysisRun:
        company = self._db.get(Company, request.company_id)
        if company is None:
            raise WorkflowInputError("Company not found", code="COMPANY_NOT_FOUND")

        products = _products_for_request(self._db, request)
        if not products:
            raise WorkflowInputError("No products found for analysis")
        found_ids = {product.id for product in products}
        missing_ids = [product_id for product_id in request.product_ids if product_id not in found_ids]
        if missing_ids:
            raise WorkflowInputError("One or more products were not found for this company")

        now_state = {
            "request": request.model_dump(mode="json"),
            "used_providers": [],
            "fallback_used_providers": [],
            "provider_breakdown": [],
            "scoring_summary": ScoringSummary().model_dump(mode="json"),
            "marketing_assets": [],
            "reports": [],
            "next_page_url": None,
        }
        analysis_run = AnalysisRun(
            company_id=request.company_id,
            status=WORKFLOW_STATUS_WAITING,
            current_step=WORKFLOW_STEPS[0].step_id,
            input_products=[_product_snapshot(product, self._db) for product in products],
            target_countries=request.target_countries,
            step_logs=_initial_step_logs(),
            workflow_state=now_state,
        )
        self._db.add(analysis_run)
        self._db.commit()
        self._db.refresh(analysis_run)
        return analysis_run

    async def run(self, analysis_id: int) -> AnalysisStatusResponse | None:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            return None

        try:
            request = AnalysisRunRequest.model_validate((analysis_run.workflow_state or {}).get("request"))
        except ValidationError:
            self._mark_run_failed(analysis_run, "Analysis request snapshot is invalid.")
            return self.status(analysis_id)

        state: dict[str, Any] = dict(analysis_run.workflow_state or {})
        context = WorkflowContext(
            db=self._db,
            analysis_run=analysis_run,
            request=request,
            data_sources=self._data_sources,
            ai_client=self._ai_client,
            state=state,
        )

        analysis_run.status = WORKFLOW_STATUS_RUNNING
        analysis_run.started_at = analysis_run.started_at or _utc_now()
        analysis_run.finished_at = None
        analysis_run.error_message = None
        analysis_run.workflow_state = _persistable_state(state)
        self._db.commit()

        for agent in self._agents:
            result = await self._run_agent_step(context, agent)
            if result is None:
                return self.status(analysis_id)

        final_state = _with_provider_summary(context.state)
        analysis_run.workflow_state = _persistable_state(final_state)
        analysis_run.status = (
            WORKFLOW_STATUS_FALLBACK_USED
            if _any_step_fallback(analysis_run.step_logs or [])
            else WORKFLOW_STATUS_SUCCESS
        )
        analysis_run.finished_at = _utc_now()
        analysis_run.current_step = WORKFLOW_STEPS[-1].step_id
        self._db.commit()
        self._db.refresh(analysis_run)
        return self.status(analysis_id)

    def status(self, analysis_id: int) -> AnalysisStatusResponse | None:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            return None
        return self._status_response(analysis_run)

    def detail(self, analysis_id: int) -> AnalysisDetailResponse | None:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            return None

        status = self._status_response(analysis_run)
        state = dict(analysis_run.workflow_state or {})
        return AnalysisDetailResponse(
            **status.model_dump(),
            input_products=analysis_run.input_products,
            target_countries=analysis_run.target_countries,
            scores=self._score_rows(analysis_run.id),
            reports=self._report_rows(analysis_run.id),
            marketing_assets=list(state.get("marketing_assets") or []),
            workflow_state=_jsonable(state),
        )

    def start_response(self, analysis_run: AnalysisRun) -> AnalysisRunStartResponse:
        return AnalysisRunStartResponse(
            analysis_id=analysis_run.id,
            status=analysis_run.status,
            current_step=analysis_run.current_step,
            status_url=f"/api/analysis/{analysis_run.id}/status",
            detail_url=f"/api/analysis/{analysis_run.id}",
            next_page_url=(analysis_run.workflow_state or {}).get("next_page_url"),
        )

    async def _run_agent_step(
        self,
        context: WorkflowContext,
        agent: "BaseWorkflowAgent",
    ) -> StepResult | None:
        step = agent.step
        started_at = _utc_now()
        start = perf_counter()
        self._update_step(
            context.analysis_run,
            step.step_id,
            {
                "status": WORKFLOW_STATUS_RUNNING,
                "started_at": started_at.isoformat(),
                "finished_at": None,
                "duration_ms": None,
                "error_code": None,
                "error_message": None,
            },
        )
        context.analysis_run.status = WORKFLOW_STATUS_RUNNING
        context.analysis_run.current_step = step.step_id
        context.analysis_run.workflow_state = _persistable_state(context.state)
        self._db.commit()

        try:
            result = await agent.run(context)
        except WorkflowInputError as exc:
            message = redact_text(str(exc)) or "Workflow input failed."
            self._fail_step(context.analysis_run, step.step_id, exc.code, message, started_at, start)
            self._mark_run_failed(context.analysis_run, message)
            return None
        except Exception:
            self._fail_step(
                context.analysis_run,
                step.step_id,
                "WORKFLOW_STEP_FAILED",
                "Workflow step failed with a sanitized internal error.",
                started_at,
                start,
            )
            self._mark_run_failed(context.analysis_run, "Workflow step failed.")
            return None

        if result.state_updates:
            context.state.update(result.state_updates)
        if result.sources:
            context.state.setdefault("provider_sources", [])
            context.state["provider_sources"].extend(result.sources)
        context.state = _with_provider_summary(context.state)
        context.analysis_run.workflow_state = _persistable_state(context.state)

        finished_at = _utc_now()
        status = WORKFLOW_STATUS_FALLBACK_USED if result.fallback_used else WORKFLOW_STATUS_SUCCESS
        self._update_step(
            context.analysis_run,
            step.step_id,
            {
                "status": status,
                "finished_at": finished_at.isoformat(),
                "duration_ms": max(0, round((perf_counter() - start) * 1000)),
                "output_summary": _jsonable(result.output_summary),
                "sources": _jsonable(result.sources or []),
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
            },
        )
        self._db.commit()
        return result

    def _status_response(self, analysis_run: AnalysisRun) -> AnalysisStatusResponse:
        state = _with_provider_summary(dict(analysis_run.workflow_state or {}))
        score_rows = _opportunity_scores(self._db, analysis_run.id)
        scoring_summary = _scoring_summary(score_rows)
        if not score_rows and state.get("scoring_summary"):
            scoring_summary = ScoringSummary.model_validate(state["scoring_summary"])

        provider_sources = _provider_sources_for_run(state, score_rows)
        used_providers, fallback_providers, breakdown = _provider_summary(provider_sources)
        next_page_url = state.get("next_page_url")
        if next_page_url is None and self._report_count(analysis_run.id) > 0:
            next_page_url = NEXT_PAGE_URL_TEMPLATE.format(analysis_id=analysis_run.id)

        return AnalysisStatusResponse(
            analysis_id=analysis_run.id,
            company_id=analysis_run.company_id,
            status=analysis_run.status,
            current_step=analysis_run.current_step,
            step_logs=[AnalysisStepLog.model_validate(log) for log in (analysis_run.step_logs or [])],
            scoring_summary=scoring_summary,
            used_providers=used_providers,
            fallback_used_providers=fallback_providers,
            provider_breakdown=breakdown,
            next_page_url=next_page_url,
            started_at=analysis_run.started_at,
            finished_at=analysis_run.finished_at,
            error_message=analysis_run.error_message,
        )

    def _update_step(self, analysis_run: AnalysisRun, step_id: str, values: dict[str, Any]) -> None:
        logs = [dict(log) for log in (analysis_run.step_logs or _initial_step_logs())]
        for log in logs:
            if log.get("step_id") == step_id:
                log.update(values)
                break
        analysis_run.step_logs = logs
        flag_modified(analysis_run, "step_logs")

    def _fail_step(
        self,
        analysis_run: AnalysisRun,
        step_id: str,
        code: str,
        message: str,
        started_at: datetime,
        start: float,
    ) -> None:
        self._update_step(
            analysis_run,
            step_id,
            {
                "status": WORKFLOW_STATUS_FAILED,
                "started_at": started_at.isoformat(),
                "finished_at": _utc_now().isoformat(),
                "duration_ms": max(0, round((perf_counter() - start) * 1000)),
                "error_code": code,
                "error_message": redact_text(message),
            },
        )
        self._db.commit()

    def _mark_run_failed(self, analysis_run: AnalysisRun, message: str) -> None:
        analysis_run.status = WORKFLOW_STATUS_FAILED
        analysis_run.finished_at = _utc_now()
        analysis_run.error_message = redact_text(message)
        self._db.commit()

    def _score_rows(self, analysis_id: int) -> list[dict[str, Any]]:
        products = {
            product.id: product
            for product in self._db.scalars(
                select(Product).where(
                    Product.id.in_(
                        {
                            row.product_id
                            for row in _opportunity_scores(self._db, analysis_id)
                        }
                        or {-1}
                    )
                )
            )
        }
        rows = []
        for row in _opportunity_scores(self._db, analysis_id):
            product = products.get(row.product_id)
            rows.append(
                _jsonable(
                    {
                        "id": row.id,
                        "analysis_id": row.analysis_id,
                        "product_id": row.product_id,
                        "product_name_cn": product.product_name_cn if product else "",
                        "product_name_en": product.product_name_en if product else None,
                        "country": row.country,
                        "trend_score": row.trend_score,
                        "price_score": row.price_score,
                        "market_score": row.market_score,
                        "supply_score": row.supply_score,
                        "logistics_score": row.logistics_score,
                        "content_score": row.content_score,
                        "total_score": row.total_score,
                        "rank": row.rank,
                        "reason": row.reason,
                        "risk": row.risk,
                        "next_action": row.next_action,
                        "fallback_used": row.fallback_used,
                        "ai_fallback_used": row.ai_fallback_used,
                        "sources": row.sources or [],
                        "evidence": row.evidence or {},
                        "competitor_analysis": row.competitor_analysis or {},
                    }
                )
            )
        return rows

    def _report_rows(self, analysis_id: int) -> list[dict[str, Any]]:
        reports = self._db.scalars(select(Report).where(Report.analysis_id == analysis_id).order_by(Report.id)).all()
        return [
            _jsonable(
                {
                    "id": report.id,
                    "analysis_id": report.analysis_id,
                    "company_id": report.company_id,
                    "title": report.title,
                    "content_markdown": report.content_markdown,
                    "content_html": report.content_html,
                    "pdf_url": report.pdf_url,
                    "created_at": report.created_at,
                    "updated_at": report.updated_at,
                }
            )
            for report in reports
        ]

    def _report_count(self, analysis_id: int) -> int:
        return self._db.scalar(select(func.count()).select_from(Report).where(Report.analysis_id == analysis_id)) or 0


class BaseWorkflowAgent:
    step: WorkflowStep

    async def run(self, context: WorkflowContext) -> StepResult:
        raise NotImplementedError


class CompanyProfilingAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[0]

    async def run(self, context: WorkflowContext) -> StepResult:
        company = context.db.get(Company, context.request.company_id)
        if company is None:
            raise WorkflowInputError("Company not found", code="COMPANY_NOT_FOUND")

        profile = {
            "id": company.id,
            "name": company.name,
            "region": company.region,
            "industry": company.industry,
            "description": company.description,
            "target_countries": context.request.target_countries,
        }
        return StepResult(
            output_summary={
                "company_id": company.id,
                "company_name": company.name,
                "target_country_count": len(context.request.target_countries),
            },
            state_updates={"company_profile": profile, "company": company},
        )


class ProductUnderstandingAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[1]

    async def run(self, context: WorkflowContext) -> StepResult:
        products = _products_for_request(context.db, context.request)
        found_ids = {product.id for product in products}
        missing_ids = [product_id for product_id in context.request.product_ids if product_id not in found_ids]
        if missing_ids:
            raise WorkflowInputError("One or more products were not found for this company")
        if not products:
            raise WorkflowInputError("No products found for analysis")

        profiles: list[dict[str, Any]] = []
        ai_fallback_used = False
        generated_keyword_count = 0
        for product in products:
            stored_keywords = _stored_keywords_for_product(context.db, product)
            keyword = stored_keywords[0] if stored_keywords else _optional_text(product.product_name_en)
            generated_keywords: list[str] = []
            keyword_source = "product_keywords" if stored_keywords else "product_name_en"
            if not stored_keywords or not _optional_text(product.product_name_en):
                try:
                    result = await generate_product_keywords(_product_keyword_request(product), context.ai_client)
                    generated_keywords = result.keywords_en[:5]
                    if not _optional_text(product.product_name_en):
                        product.product_name_en = result.product_name_en
                    saved_keywords = _persist_generated_keywords(context.db, product, result.keywords_en)
                    stored_keywords = _stored_keywords_for_product(context.db, product)
                    generated_keyword_count += saved_keywords
                    keyword = generated_keywords[0] if generated_keywords else result.product_name_en
                    keyword_source = "bailian_generated"
                except (BailianError, AiStructuredOutputError):
                    ai_fallback_used = True
                    keyword = keyword or _fallback_keyword(product)
                    keyword_source = "product_fields_fallback"
            if not keyword:
                keyword = _fallback_keyword(product)
                keyword_source = "product_fields_fallback"

            profiles.append(
                _jsonable(
                    {
                        **_product_snapshot(product, context.db),
                        "keyword": keyword,
                        "keyword_source": keyword_source,
                        "product_keywords": stored_keywords,
                        "generated_keywords": generated_keywords,
                        "intake_source": _intake_source_for_product(context.db, product),
                        "hs_code": _infer_hs_code(" ".join([product.category or "", keyword, product.description or ""])),
                    }
                )
            )
        context.analysis_run.input_products = [_product_snapshot(product, context.db) for product in products]

        sources = [
            _source(
                "bailian",
                "AI fallback template" if ai_fallback_used else ("qwen3.6-plus" if generated_keyword_count else "Existing product fields"),
                "ai_fallback" if ai_fallback_used else (API_SOURCE if generated_keyword_count else "local"),
                ai_fallback_used,
                bool(generated_keyword_count),
                "Product keyword understanding uses existing keywords first, qwen3.6-plus when fields are missing, and deterministic fallback when AI is unavailable.",
            )
        ]
        return StepResult(
            output_summary={
                "product_count": len(profiles),
                "keyword_count": sum(1 for item in profiles if item.get("keyword")),
                "generated_keyword_count": generated_keyword_count,
                "ai_fallback_used": ai_fallback_used,
            },
            state_updates={"products": products, "product_profiles": profiles},
            sources=sources,
            fallback_used=ai_fallback_used,
            fallback_reason="Bailian product keyword generation fallback was used." if ai_fallback_used else None,
        )


class DataCollectionAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[2]

    async def run(self, context: WorkflowContext) -> StepResult:
        raw_signals: dict[str, dict[str, Any]] = {}
        summaries: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        fallback_providers: set[str] = set()
        provider_call_count = 0

        market_profiles: dict[str, Any] = {}
        for country in context.request.target_countries:
            provider_call_count += 1
            market_profiles[country] = await context.data_sources.get_market_profile(country)
            sources.append(_source_from_response("worldbank", market_profiles[country], "World Bank market profile"))
            if market_profiles[country].fallback_used:
                fallback_providers.add("worldbank")

        for product in context.state.get("product_profiles", []):
            keyword = str(product.get("keyword") or product.get("product_name_en") or product.get("product_name_cn"))
            category = str(product.get("category") or keyword)
            hs_code = str(product.get("hs_code") or _infer_hs_code(category))
            for country in context.request.target_countries:
                provider_call_count += 3
                competitors = await context.data_sources.search_competitors(
                    keyword,
                    country=country,
                    limit=context.request.competitor_limit,
                )
                content = await context.data_sources.get_content_trends(keyword, country=country, limit=20)
                trade = await context.data_sources.get_trade_data(category, hs_code=hs_code, country=country)

                key = _product_country_key(int(product["id"]), country)
                raw_signals[key] = {
                    "product": product,
                    "country": country,
                    "competitors": competitors,
                    "content": content,
                    "market": market_profiles[country],
                    "trade": trade,
                }
                summaries.append(
                    {
                        "product_id": product["id"],
                        "country": country,
                        "competitor_items": len(competitors.items),
                        "content_items": len(content.items),
                        "market_indicators": len(market_profiles[country].indicators),
                        "trade_records": len(trade.records),
                    }
                )
                for provider, response, label in (
                    ("etsy", competitors, "Etsy competitor search"),
                    ("data_source_service", content, "Unified content trends"),
                    ("un_comtrade", trade, "UN Comtrade trade data"),
                ):
                    sources.append(_source_from_response(provider, response, label))
                    if bool(getattr(response, "fallback_used", False)):
                        fallback_providers.add(provider)

        return StepResult(
            output_summary={
                "provider_call_count": provider_call_count,
                "fallback_providers": sorted(fallback_providers),
                "record_count": sum(
                    item["competitor_items"] + item["content_items"] + item["market_indicators"] + item["trade_records"]
                    for item in summaries
                ),
            },
            state_updates={"raw_signals": raw_signals, "data_collection_summary": summaries},
            sources=sources,
            fallback_used=bool(fallback_providers),
            fallback_reason="One or more provider calls used cache/CSV fallback." if fallback_providers else None,
        )


class CompetitorAnalysisAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[3]

    async def run(self, context: WorkflowContext) -> StepResult:
        results: list[dict[str, Any]] = []
        fallback_used = False
        for signal in (context.state.get("raw_signals") or {}).values():
            product = signal["product"]
            country = signal["country"]
            competitors = signal["competitors"]
            analysis = analyze_competitors(
                keyword=str(product.get("keyword") or product.get("product_name_en") or product.get("product_name_cn")),
                country=country,
                competitor_items=competitors.items,
            )
            fallback_used = fallback_used or competitors.fallback_used
            results.append({"product_id": product["id"], "country": country, **analysis.model_dump(mode="json")})

        return StepResult(
            output_summary={
                "analysis_count": len(results),
                "item_count": sum(int(item.get("item_count", 0)) for item in results),
                "competition_levels": sorted({str(item.get("competition_level")) for item in results if item.get("competition_level")}),
            },
            state_updates={"competitor_analysis": results},
            sources=[
                _source(
                    "etsy",
                    "Etsy API or competitor_samples.csv",
                    CSV_FALLBACK_SOURCE if fallback_used else API_SOURCE,
                    fallback_used,
                    not fallback_used,
                    "Competitor rows are analyzed with deterministic Python logic.",
                )
            ],
            fallback_used=fallback_used,
            fallback_reason="Competitor analysis used CSV fallback rows." if fallback_used else None,
        )


class MarketProfilingAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[4]

    async def run(self, context: WorkflowContext) -> StepResult:
        service = MarketProfileAnalysisService(context.data_sources, ai_client=context.ai_client)
        results: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        fallback_used = False
        ai_fallback_used = False
        seen: set[tuple[int, str]] = set()

        for product in context.state.get("product_profiles", []):
            for country in context.request.target_countries:
                key = (int(product["id"]), country)
                if key in seen:
                    continue
                seen.add(key)
                response = await service.analyze_country(
                    country,
                    str(product.get("category") or product.get("keyword") or "product"),
                    keyword=str(product.get("keyword") or ""),
                    hs_code=str(product.get("hs_code") or ""),
                )
                fallback_used = fallback_used or response.fallback_used
                ai_fallback_used = ai_fallback_used or response.ai_fallback_used
                sources.extend([source.model_dump(mode="json") for source in response.sources])
                results.append(
                    {
                        "product_id": product["id"],
                        "country": country,
                        "summary": response.summary,
                        "market_size_score": response.market_size_score,
                        "trade_score": response.trade_score,
                        "logistics_score": response.logistics_score,
                        "competition_level": response.competition_level,
                    }
                )

        return StepResult(
            output_summary={
                "profile_count": len(results),
                "fallback_used": fallback_used,
                "ai_fallback_used": ai_fallback_used,
            },
            state_updates={"market_profiles": results},
            sources=sources,
            fallback_used=fallback_used or ai_fallback_used,
            fallback_reason="Market profiling used data or AI fallback." if fallback_used or ai_fallback_used else None,
        )


class ContentTrendAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[5]

    async def run(self, context: WorkflowContext) -> StepResult:
        service = ContentTrendAnalysisService(context.data_sources, ai_client=context.ai_client)
        results: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        fallback_used = False
        ai_fallback_used = False

        for product in context.state.get("product_profiles", []):
            keyword = str(product.get("keyword") or product.get("product_name_en") or product.get("product_name_cn"))
            for country in context.request.target_countries:
                response = await service.analyze(keyword, country)
                fallback_used = fallback_used or response.fallback_used
                ai_fallback_used = ai_fallback_used or response.ai_fallback_used
                sources.extend([source.model_dump(mode="json") for source in response.sources])
                results.append(
                    {
                        "product_id": product["id"],
                        "country": country,
                        "keyword": response.keyword,
                        "content_themes": response.content_themes[:5],
                        "marketing_angles": response.marketing_angles[:5],
                        "pain_points": response.pain_points[:5],
                        "source_item_count": len(response.source_items),
                    }
                )

        return StepResult(
            output_summary={
                "trend_count": len(results),
                "source_item_count": sum(int(item["source_item_count"]) for item in results),
                "fallback_used": fallback_used,
                "ai_fallback_used": ai_fallback_used,
            },
            state_updates={"content_trends": results},
            sources=sources,
            fallback_used=fallback_used or ai_fallback_used,
            fallback_reason="Content trend analysis used provider or AI fallback." if fallback_used or ai_fallback_used else None,
        )


class OpportunityScoringAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[6]

    async def run(self, context: WorkflowContext) -> StepResult:
        service = OpportunityScoringService(context.db, context.data_sources, ai_client=context.ai_client)
        response = await service.run_for_analysis(
            ScoringRunRequest(
                company_id=context.request.company_id,
                product_ids=context.request.product_ids,
                target_countries=context.request.target_countries,
                competitor_limit=context.request.competitor_limit,
            ),
            analysis_run=context.analysis_run,
            final_status=None,
        )
        scoring_summary = ScoringSummary(
            item_count=response.item_count,
            top_score=response.items[0].total_score if response.items else None,
            top_product_id=response.items[0].product_id if response.items else None,
            top_country=response.items[0].country if response.items else None,
            fallback_used=response.fallback_used,
            ai_fallback_used=response.ai_fallback_used,
        )
        sources = [source.model_dump(mode="json") for source in response.sources]
        return StepResult(
            output_summary=scoring_summary.model_dump(mode="json"),
            state_updates={
                "scoring_summary": scoring_summary.model_dump(mode="json"),
                "score_items": [item.model_dump(mode="json") for item in response.items[:10]],
            },
            sources=sources,
            fallback_used=response.fallback_used or response.ai_fallback_used,
            fallback_reason="Opportunity scoring used provider or AI fallback." if response.fallback_used or response.ai_fallback_used else None,
        )


class MarketingPrepAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[7]

    async def run(self, context: WorkflowContext) -> StepResult:
        score_rows = _opportunity_scores(context.db, context.analysis_run.id)[:3]
        assets: list[dict[str, Any]] = []
        ai_fallback_used = False
        for row in score_rows:
            product = context.db.get(Product, row.product_id)
            if product is None:
                continue
            target_language = "ja" if row.country.upper().startswith("JP") else "en"
            keywords = _keywords_for_product(context.db, product)[:5]
            try:
                copy = await _marketing_copy(
                    context.ai_client,
                    product_name=product.product_name_en or product.product_name_cn,
                    product_description=product.description,
                    country=row.country,
                    target_language=target_language,
                    keywords=keywords,
                    selling_points=_selling_points_from_score(row),
                )
            except (BailianError, AiJsonParseError, ValidationError, ValueError, TypeError):
                ai_fallback_used = True
                copy = _fallback_marketing_copy(product, row.country, keywords)
            assets.append(
                {
                    "product_id": product.id,
                    "country": row.country,
                    "target_language": target_language,
                    **copy.model_dump(mode="json"),
                }
            )

        return StepResult(
            output_summary={"asset_count": len(assets), "ai_fallback_used": ai_fallback_used},
            state_updates={"marketing_assets": assets},
            sources=[
                _source(
                    "bailian",
                    "qwen3.6-plus" if not ai_fallback_used else "AI fallback template",
                    API_SOURCE if not ai_fallback_used else "ai_fallback",
                    ai_fallback_used,
                    not ai_fallback_used,
                    "Generates localized marketing copy or deterministic fallback assets.",
                )
            ],
            fallback_used=ai_fallback_used,
            fallback_reason="Marketing copy used deterministic fallback." if ai_fallback_used else None,
        )


class ReportPrepAgent(BaseWorkflowAgent):
    step = WORKFLOW_STEPS[8]

    async def run(self, context: WorkflowContext) -> StepResult:
        try:
            outcome = await ReportGenerator(context.db, ai_client=context.ai_client).generate_from_analysis(
                context.analysis_run.id,
                force_regenerate=False,
            )
        except ReportGenerationInputError as exc:
            raise WorkflowInputError(str(exc), code=exc.code) from exc

        report = outcome.report
        next_page_url = NEXT_PAGE_URL_TEMPLATE.format(analysis_id=context.analysis_run.id)
        state = dict(context.analysis_run.workflow_state or context.state)
        reports = list(state.get("reports") or [])
        context.state = state
        return StepResult(
            output_summary={
                "report_id": report.id,
                "section_count": 13,
                "markdown_length": len(report.content_markdown or ""),
                "html_length": len(report.content_html or ""),
                "ai_fallback_used": outcome.ai_fallback_used,
                "reused_existing": outcome.reused_existing,
            },
            state_updates={"reports": reports, "next_page_url": next_page_url},
            sources=[
                _source(
                    "bailian",
                    "qwen3.6-plus" if not outcome.ai_fallback_used else "AI fallback template",
                    API_SOURCE if not outcome.ai_fallback_used else "ai_fallback",
                    outcome.ai_fallback_used,
                    not outcome.ai_fallback_used,
                    "Creates or reuses a structured 13-section export report.",
                )
            ],
            fallback_used=outcome.ai_fallback_used,
            fallback_reason="Report generation used deterministic fallback." if outcome.ai_fallback_used else None,
        )


async def run_export_insight_workflow_background(analysis_id: int) -> None:
    db = SessionLocal()
    try:
        data_sources = DataSourceService(db)
        workflow = ExportInsightWorkflow(db, data_sources, ai_client=BailianClient())
        await workflow.run(analysis_id)
    finally:
        db.close()


def _initial_step_logs() -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.step_id,
            "node": step.node,
            "title": step.title,
            "status": WORKFLOW_STATUS_WAITING,
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "input_summary": {},
            "output_summary": {},
            "sources": [],
            "fallback_used": False,
            "fallback_reason": None,
            "error_code": None,
            "error_message": None,
        }
        for step in WORKFLOW_STEPS
    ]


def _products_for_request(db: Session, request: AnalysisRunRequest) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .where(
                Product.company_id == request.company_id,
                Product.id.in_(request.product_ids),
            )
            .order_by(Product.id)
        )
    )


def _product_snapshot(product: Product, db: Session | None = None) -> dict[str, Any]:
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


def _product_keyword_request(product: Product) -> ProductKeywordsRequest:
    return ProductKeywordsRequest(
        product_name_cn=product.product_name_cn,
        product_name_en=product.product_name_en,
        category=product.category,
        material=product.material,
        certification=product.certification,
        cost_price_cny=str(product.cost_price_cny) if product.cost_price_cny is not None else None,
        weight_kg=str(product.weight_kg) if product.weight_kg is not None else None,
        package_size=product.package_size,
        moq=product.moq,
        description=product.description,
    )


def _keywords_for_product(db: Session, product: Product) -> list[str]:
    keywords = _stored_keywords_for_product(db, product)
    if keywords:
        return keywords
    return [_fallback_keyword(product)]


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


def _persist_generated_keywords(db: Session, product: Product, keywords: list[str]) -> int:
    existing = {
        (keyword or "").casefold()
        for keyword in db.scalars(
            select(ProductKeyword.keyword).where(ProductKeyword.product_id == product.id)
        )
    }
    saved_count = 0
    for value in keywords:
        keyword = _optional_text(value)
        if not keyword:
            continue
        key = keyword.casefold()
        if key in existing:
            continue
        db.add(
            ProductKeyword(
                product_id=product.id,
                keyword=keyword[:255],
                language="en",
                country=None,
                source="bailian",
            )
        )
        existing.add(key)
        saved_count += 1
    if saved_count or product in db.dirty:
        db.flush()
    return saved_count


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


def _fallback_keyword(product: Product) -> str:
    for candidate in (product.product_name_en, product.category, product.product_name_cn):
        text = _optional_text(candidate)
        if text:
            return text
    return f"product {product.id}"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _product_country_key(product_id: int, country: str) -> str:
    return f"{product_id}:{country.upper()}"


def _source(
    provider: str,
    label: str,
    source_type: str,
    fallback_used: bool,
    api_invoked: bool,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "source_label": label,
        "source_type": source_type,
        "fallback_used": fallback_used,
        "api_invoked": api_invoked,
        "detail": detail,
    }


def _source_from_response(provider: str, response: Any, label: str) -> dict[str, Any]:
    fallback_used = bool(getattr(response, "fallback_used", False))
    return _source(
        provider,
        f"CSV fallback: {label}" if fallback_used else label,
        CSV_FALLBACK_SOURCE if fallback_used else API_SOURCE,
        fallback_used,
        not fallback_used,
        "Provider response was normalized by DataSourceService.",
    )


def _with_provider_summary(state: dict[str, Any]) -> dict[str, Any]:
    provider_sources = list(state.get("provider_sources") or [])
    used_providers, fallback_providers, breakdown = _provider_summary(provider_sources)
    state["used_providers"] = used_providers
    state["fallback_used_providers"] = fallback_providers
    state["provider_breakdown"] = [item.model_dump(mode="json") for item in breakdown]
    return state


def _provider_summary(
    sources: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[ProviderBreakdownItem]]:
    grouped: dict[str, dict[str, Any]] = {}
    for source in sources:
        provider = str(source.get("provider") or "").strip()
        if not provider or provider in OPTIONAL_PROVIDERS:
            continue
        item = grouped.setdefault(
            provider,
            {"source_types": set(), "labels": set(), "api_invoked": False, "fallback_used": False},
        )
        source_type = str(source.get("source_type") or "").strip()
        label = str(source.get("source_label") or "").strip()
        if source_type:
            item["source_types"].add(source_type)
        if label:
            item["labels"].add(label)
        item["api_invoked"] = bool(item["api_invoked"] or source.get("api_invoked"))
        item["fallback_used"] = bool(item["fallback_used"] or source.get("fallback_used"))

    breakdown = [
        ProviderBreakdownItem(
            provider=provider,
            source_types=sorted(values["source_types"]),
            labels=sorted(values["labels"]),
            api_invoked=bool(values["api_invoked"]),
            fallback_used=bool(values["fallback_used"]),
        )
        for provider, values in sorted(grouped.items())
    ]
    return (
        [item.provider for item in breakdown],
        [item.provider for item in breakdown if item.fallback_used],
        breakdown,
    )


def _provider_sources_for_run(state: dict[str, Any], score_rows: list[OpportunityScore]) -> list[dict[str, Any]]:
    sources = list(state.get("provider_sources") or [])
    for row in score_rows:
        sources.extend(row.sources or [])
    for log in state.get("step_logs") or []:
        if isinstance(log, dict):
            sources.extend(log.get("sources") or [])
    return [_jsonable(source) for source in sources if isinstance(source, dict)]


def _opportunity_scores(db: Session, analysis_id: int) -> list[OpportunityScore]:
    return list(
        db.scalars(
            select(OpportunityScore)
            .where(OpportunityScore.analysis_id == analysis_id)
            .order_by(OpportunityScore.rank.asc(), OpportunityScore.total_score.desc())
        )
    )


def _scoring_summary(rows: list[OpportunityScore]) -> ScoringSummary:
    top = rows[0] if rows else None
    return ScoringSummary(
        item_count=len(rows),
        top_score=Decimal(str(top.total_score)) if top and top.total_score is not None else None,
        top_product_id=top.product_id if top else None,
        top_country=top.country if top else None,
        fallback_used=any(row.fallback_used for row in rows),
        ai_fallback_used=any(row.ai_fallback_used for row in rows),
    )


def _any_step_fallback(logs: list[dict[str, Any]]) -> bool:
    return any(log.get("status") == WORKFLOW_STATUS_FALLBACK_USED or log.get("fallback_used") for log in logs)


async def _marketing_copy(
    ai_client: BailianClient,
    *,
    product_name: str,
    product_description: str | None,
    country: str,
    target_language: str,
    keywords: list[str],
    selling_points: list[str],
) -> MarketingCopyResponse:
    payload = {
        "product_name": product_name,
        "product_description": product_description,
        "target_country": country,
        "target_language": target_language,
        "platform": "cross-border ecommerce",
        "tone": "professional",
        "keywords": keywords,
        "selling_points": selling_points,
    }
    result = await ai_client.chat(build_marketing_copy_messages(payload), temperature=0.5, max_tokens=1000, json_mode=True)
    return MarketingCopyResponse.model_validate(parse_json_object(result.content))


def _fallback_marketing_copy(product: Product, country: str, keywords: list[str]) -> MarketingCopyResponse:
    product_name = product.product_name_en or product.product_name_cn
    seo_keywords = keywords or [product_name]
    return MarketingCopyResponse(
        listing_title=f"{product_name} for {country} buyers",
        short_description=f"{product_name} with export-ready product information and conservative claims.",
        bullet_points=[
            "Material, size, packaging, and care details should be shown clearly.",
            "Position against competitor price bands before paid launch.",
            "Validate claims, labeling, and platform rules before publishing.",
        ],
        ad_copy=f"Explore {product_name} for localized home and lifestyle merchandising in {country}.",
        social_posts=[
            f"New {product_name} concept for {country}: practical details, clear materials, and export-ready packaging.",
        ],
        seo_keywords=seo_keywords,
        localization_notes=[
            "Use localized measurements and cautious wording.",
            "Do not claim certifications or performance unless independently verified.",
        ],
    )


def _selling_points_from_score(row: OpportunityScore) -> list[str]:
    evidence = row.evidence or {}
    competitor = row.competitor_analysis or {}
    return [
        str(row.reason or "Opportunity score generated by backend model."),
        str(competitor.get("price_suggestion") or "Validate price band with marketplace evidence."),
        f"Computed total score: {row.total_score}" if row.total_score is not None else "Computed score is available.",
        f"Keyword: {evidence.get('keyword')}" if evidence.get("keyword") else "Use product keyword evidence from scoring.",
    ]


async def _report_section(
    ai_client: BailianClient,
    *,
    company_name: str,
    analysis_id: int,
    state: dict[str, Any],
) -> ReportSectionResponse:
    payload = {
        "section_type": "executive_summary",
        "product_name": company_name,
        "target_country": None,
        "language": "zh",
        "market_context": {
            "analysis_id": analysis_id,
            "scoring_summary": state.get("scoring_summary"),
            "used_providers": state.get("used_providers"),
            "fallback_used_providers": state.get("fallback_used_providers"),
        },
    }
    result = await ai_client.chat(build_report_section_messages(payload), temperature=0.4, max_tokens=900, json_mode=True)
    return ReportSectionResponse.model_validate(parse_json_object(result.content))


def _fallback_report_intro(company_name: str, analysis_id: int, state: dict[str, Any]) -> str:
    scoring = state.get("scoring_summary") or {}
    item_count = scoring.get("item_count", 0) if isinstance(scoring, dict) else 0
    return (
        f"Analysis #{analysis_id} for {company_name} completed with {item_count} product-country score rows. "
        "Some sections may use CSV fallback or deterministic AI fallback; treat results as directional demo evidence."
    )


def _report_markdown(
    *,
    company: Company,
    analysis_id: int,
    intro_markdown: str,
    score_rows: list[OpportunityScore],
    state: dict[str, Any],
) -> str:
    top_rows = score_rows[:5]
    provider_line = ", ".join(state.get("used_providers") or []) or "csv_fallback"
    fallback_line = ", ".join(state.get("fallback_used_providers") or []) or "none"
    score_lines = "\n".join(
        [
            f"- Rank {row.rank}: product {row.product_id} in {row.country}, total score {row.total_score}. "
            f"Next action: {row.next_action or 'Validate with live evidence.'}"
            for row in top_rows
        ]
    ) or "- No score rows were generated."
    marketing_lines = "\n".join(
        [
            f"- Product {asset.get('product_id') or asset.get('product')} / {asset.get('country')}: "
            f"{asset.get('listing_title') or asset.get('title')}"
            for asset in (state.get("marketing_assets") or [])[:5]
            if isinstance(asset, dict)
        ]
    ) or "- Marketing assets were not generated."
    data_notes = [
        "World Bank, GDELT, YouTube, Etsy, optional UN Comtrade, and CSV fallback are the supported R17 sources.",
        "eBay, Rakuten, and Reddit are not required runtime providers and were not called by this workflow.",
        "AI sections use Bailian when configured and deterministic fallback otherwise.",
    ]
    return "\n\n".join(
        [
            f"# Export Insight Report #{analysis_id}",
            f"Company: {company.name}",
            "## Executive Summary",
            intro_markdown,
            "## Top Opportunities",
            score_lines,
            "## Marketing Prep",
            marketing_lines,
            "## Data Sources",
            f"Used providers: {provider_line}",
            f"Fallback providers: {fallback_line}",
            "## Data Limitations",
            "\n".join(f"- {note}" for note in data_notes),
        ]
    )


def _persistable_state(state: dict[str, Any]) -> dict[str, Any]:
    skipped = {"company", "products", "raw_signals"}
    return _jsonable({key: value for key, value in state.items() if key not in skipped})


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(str(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
