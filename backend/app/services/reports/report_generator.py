from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import AnalysisRun, Company, OpportunityScore, Product, ProductDraft, Report
from app.schemas import ReportCreate, ReportUpdate
from app.services import report_service
from app.services.ai import BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_report_generation_messages
from app.services.ai.qwen_timeout import wait_for_qwen
from app.services.analysis_performance import is_timeout_error, mark_latest_qwen_fallback
from app.services.dashboard_service import DashboardService


REPORT_TITLE = "《南通家纺企业海外市场出海选品洞察报告》"
REPORT_SECTION_TITLES = (
    "企业画像",
    "产品清单",
    "数据源说明",
    "目标国家市场概览",
    "产品机会评分排名",
    "竞品价格区间",
    "内容趋势与用户痛点",
    "推荐产品与推荐理由",
    "定价建议",
    "英文标题与五点描述",
    "短视频与社媒内容建议",
    "风险提示",
    "下一步行动计划",
)

INTAKE_CONFIRMATION_NOTE = "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。"
INTAKE_SOURCE_BOUNDARY_LINES = (
    "- 国内商品截图/链接用于识别企业可供产品信息。",
    "- 海外机会评分仍基于海外竞品样本、内容趋势、国家市场画像与贸易数据。",
    "- 国内链接价格不代表海外销售价格，不作为海外竞品价格、成交价、采购成本或利润依据。",
)

FORBIDDEN_REPORT_CLAIMS = (
    "销量预测",
    "销售预测",
    "销售额预测",
    "利润预测",
    "GMV",
    "爆款",
    "平台排名",
    "已验证成交额",
    "保证转化",
    "保证销量",
    "清关确定",
    "关税确定",
    "认证有效",
    "best-selling",
    "bestseller",
    "sales forecast",
    "sales prediction",
    "profit forecast",
    "gmv forecast",
    "guaranteed conversion",
    "guaranteed sales",
    "customs cleared",
    "no.1",
    "no 1",
)


class ReportGenerationInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ReportGenerationOutcome:
    report: Report
    ai_fallback_used: bool
    reused_existing: bool = False


class ReportGenerator:
    def __init__(
        self,
        db: Session,
        *,
        ai_client: BailianClient | None = None,
        ai_timeout_seconds: float | None = None,
        force_deterministic: bool = False,
    ) -> None:
        self._db = db
        self._ai_client = ai_client or BailianClient()
        self._ai_timeout_seconds = ai_timeout_seconds
        self._force_deterministic = force_deterministic

    async def generate_from_analysis(
        self,
        analysis_id: int,
        *,
        force_regenerate: bool = False,
    ) -> ReportGenerationOutcome:
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            raise ReportGenerationInputError("ANALYSIS_NOT_FOUND", "Analysis run not found.")

        company = self._db.get(Company, analysis_run.company_id)
        if company is None:
            raise ReportGenerationInputError("COMPANY_NOT_FOUND", "Company not found.")

        existing = self._existing_report(analysis_id)
        if existing is not None and not force_regenerate:
            if existing.content_markdown and not existing.content_html:
                existing = report_service.update_report(
                    self._db,
                    existing,
                    ReportUpdate(content_html=render_report_html(existing.content_markdown)),
                )
            self._persist_report_state(analysis_run, existing, ai_fallback_used=False)
            return ReportGenerationOutcome(existing, ai_fallback_used=False, reused_existing=True)

        report_input = self._report_input(analysis_run, company)
        deterministic_markdown = _build_deterministic_markdown(report_input)
        content_markdown, ai_fallback_used = await self._ai_or_fallback_markdown(
            report_input,
            deterministic_markdown,
        )
        content_html = render_report_html(content_markdown)
        report = report_service.create_report(
            self._db,
            ReportCreate(
                analysis_id=analysis_run.id,
                company_id=company.id,
                title=REPORT_TITLE,
                content_markdown=content_markdown,
                content_html=content_html,
                pdf_url=None,
            ),
        )
        self._persist_report_state(analysis_run, report, ai_fallback_used=ai_fallback_used)
        return ReportGenerationOutcome(report, ai_fallback_used=ai_fallback_used)

    def _existing_report(self, analysis_id: int) -> Report | None:
        return self._db.scalar(
            select(Report)
            .where(Report.analysis_id == analysis_id, Report.title == REPORT_TITLE)
            .order_by(Report.id.desc())
            .limit(1)
        )

    def _report_input(self, analysis_run: AnalysisRun, company: Company) -> dict[str, Any]:
        score_rows = list(
            self._db.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.analysis_id == analysis_run.id)
                .order_by(OpportunityScore.rank.asc(), OpportunityScore.total_score.desc())
            )
        )
        products = _products_by_id(self._db, analysis_run, score_rows)
        product_snapshots = _product_snapshots_by_id(analysis_run.input_products or [])
        state = dict(analysis_run.workflow_state or {})
        dashboard = DashboardService(self._db).get_dashboard(analysis_run.id)
        dashboard_payload = dashboard.model_dump(mode="json") if dashboard is not None else {}
        source_rows = _collect_sources(analysis_run, state, score_rows, dashboard_payload)

        return _jsonable(
            {
                "report_title": REPORT_TITLE,
                "generated_from": "structured_analysis_result",
                "analysis": {
                    "analysis_id": analysis_run.id,
                    "status": analysis_run.status,
                    "target_countries": analysis_run.target_countries or [],
                    "started_at": analysis_run.started_at,
                    "finished_at": analysis_run.finished_at,
                },
                "company": {
                    "id": company.id,
                    "name": company.name,
                    "region": company.region,
                    "industry": company.industry,
                    "description": company.description,
                    "target_countries": company.target_countries or analysis_run.target_countries or [],
                },
                "products": [
                    _product_payload(product, product_snapshots.get(product_id), self._db)
                    for product_id, product in sorted(products.items())
                ],
                "product_profiles": _record_list(state.get("product_profiles")),
                "market_profiles": _record_list(state.get("market_profiles")),
                "content_trends": _record_list(state.get("content_trends")),
                "marketing_assets": _record_list(state.get("marketing_assets")),
                "scores": [
                    _score_payload(row, products.get(row.product_id), product_snapshots.get(row.product_id), self._db)
                    for row in score_rows
                ],
                "dashboard": dashboard_payload,
                "data_sources": source_rows,
                "policy": {
                    "data_boundary": "Use only structured fields in this payload.",
                    "sales_claim": "Platform samples are directional price/content signals and do not represent real sales.",
                    "intake_source_boundary": list(INTAKE_SOURCE_BOUNDARY_LINES),
                    "prohibited_claims": list(FORBIDDEN_REPORT_CLAIMS),
                    "pdf_status": "PDF export is not implemented in v1.",
                },
            }
        )

    async def _ai_or_fallback_markdown(
        self,
        report_input: dict[str, Any],
        deterministic_markdown: str,
    ) -> tuple[str, bool]:
        payload = {
            "report_input": _compact_report_input(report_input),
            "required_title": REPORT_TITLE,
            "required_sections": list(REPORT_SECTION_TITLES),
            "output_contract": {"content_markdown": "string"},
        }
        if self._force_deterministic:
            fallback = _ensure_intake_source_markdown(deterministic_markdown, report_input)
            _validate_report_markdown(fallback)
            return fallback, False
        try:
            result = await wait_for_qwen(
                self._ai_client.chat(
                    build_report_generation_messages(payload),
                    temperature=0.25,
                    max_tokens=3600,
                    json_mode=True,
                ),
                timeout_seconds=self._ai_timeout_seconds,
            )
            parsed = parse_json_object(result.content)
            content_markdown = parsed.get("content_markdown")
            if not isinstance(content_markdown, str) or not content_markdown.strip():
                raise ValueError("AI response did not include content_markdown.")
            content_markdown = _normalize_ai_markdown(content_markdown)
            content_markdown = _ensure_intake_source_markdown(content_markdown, report_input)
            _validate_report_markdown(content_markdown)
            return content_markdown, False
        except (BailianError, AiJsonParseError, ValueError, TypeError, TimeoutError) as exc:
            mark_latest_qwen_fallback("report_generation_timeout" if is_timeout_error(exc) else "report_generation")
            fallback = _ensure_intake_source_markdown(_fallback_notice(deterministic_markdown), report_input)
            _validate_report_markdown(fallback)
            return fallback, True

    def _persist_report_state(
        self,
        analysis_run: AnalysisRun,
        report: Report,
        *,
        ai_fallback_used: bool,
    ) -> None:
        state = dict(analysis_run.workflow_state or {})
        reports = [dict(item) for item in state.get("reports", []) if isinstance(item, dict)]
        record = {
            "id": report.id,
            "title": report.title,
            "analysis_id": report.analysis_id,
            "next_page_url": f"/reports/{report.id}",
            "list_page_url": f"/reports?analysis_id={report.analysis_id}",
            "ai_fallback_used": ai_fallback_used,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
        reports = [item for item in reports if item.get("id") != report.id]
        reports.append(record)
        state["reports"] = reports
        state["next_page_url"] = f"/reports?analysis_id={report.analysis_id}"
        state["report_generation"] = {
            "latest_report_id": report.id,
            "ai_fallback_used": ai_fallback_used,
            "pdf_export": "not_implemented",
        }
        analysis_run.workflow_state = state
        flag_modified(analysis_run, "workflow_state")
        self._db.commit()


def render_report_html(markdown: str) -> str:
    lines = markdown.splitlines()
    parts: list[str] = ['<article class="report-content">']
    paragraph: list[str] = []
    list_tag: str | None = None
    in_code = False
    code_lines: list[str] = []
    table_rows: list[list[str]] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            parts.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            parts.append(f"</{list_tag}>")
            list_tag = None

    def flush_table() -> None:
        nonlocal table_rows
        if not table_rows:
            return
        parts.append("<table><tbody>")
        for row in table_rows:
            tag = "th" if not parts[-1].endswith("</tr>") else "td"
            cells = "".join(f"<{tag}>{html.escape(cell)}</{tag}>" for cell in row)
            parts.append(f"<tr>{cells}</tr>")
        parts.append("</tbody></table>")
        table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            flush_table()
            if in_code:
                parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            flush_table()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            flush_table()
            level = len(heading.group(1))
            parts.append(f"<h{level}>{html.escape(heading.group(2).strip())}</h{level}>")
            continue
        if stripped == "---":
            flush_paragraph()
            close_list()
            flush_table()
            parts.append("<hr>")
            continue
        if _is_table_line(stripped):
            flush_paragraph()
            close_list()
            if _is_table_separator(stripped):
                continue
            table_rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
            continue
        flush_table()
        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+[.]\s+(.+)$", stripped)
        if unordered or ordered:
            flush_paragraph()
            wanted = "ul" if unordered else "ol"
            if list_tag != wanted:
                close_list()
                list_tag = wanted
                parts.append(f"<{wanted}>")
            text = (unordered or ordered).group(1)
            parts.append(f"<li>{html.escape(text)}</li>")
            continue
        close_list()
        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    flush_table()
    if in_code:
        parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    parts.append("</article>")
    return "\n".join(parts)


def _build_deterministic_markdown(report_input: dict[str, Any]) -> str:
    sections = [
        f"# {REPORT_TITLE}",
        (
            "> 本报告仅基于本次分析流程中的企业、产品、公开数据源、CSV fallback、"
            "机会评分、看板聚合和营销素材生成。平台竞品样本只表示价格区间和内容方向信号，"
            "不代表真实销量或成交表现。"
        ),
        _section(1, "企业画像", _company_lines(report_input)),
        _section(2, "产品清单", _product_lines(report_input)),
        _section(3, "数据源说明", _source_lines(report_input)),
        _section(4, "目标国家市场概览", _market_profile_lines(report_input)),
        _section(5, "产品机会评分排名", _score_ranking_lines(report_input)),
        _section(6, "竞品价格区间", _price_range_lines(report_input)),
        _section(7, "内容趋势与用户痛点", _content_trend_lines(report_input)),
        _section(8, "推荐产品与推荐理由", _recommendation_lines(report_input)),
        _section(9, "定价建议", _pricing_lines(report_input)),
        _section(10, "英文标题与五点描述", _marketing_listing_lines(report_input)),
        _section(11, "短视频与社媒内容建议", _social_content_lines(report_input)),
        _section(12, "风险提示", _risk_lines(report_input)),
        _section(13, "下一步行动计划", _next_action_lines(report_input)),
    ]
    return "\n\n".join(sections)


def _section(index: int, title: str, lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "- 本节暂无可用结构化数据。"
    return f"## {index}. {title}\n{body}"


def _company_lines(report_input: dict[str, Any]) -> list[str]:
    company = report_input["company"]
    analysis = report_input["analysis"]
    return [
        f"- 企业名称：{_safe_text(company.get('name'))}",
        f"- 所在地区：{_safe_text(company.get('region')) or '未填写'}",
        f"- 所属行业：{_safe_text(company.get('industry')) or '未填写'}",
        f"- 企业描述：{_safe_text(company.get('description')) or '未填写'}",
        f"- 本次目标国家：{_join_values(analysis.get('target_countries')) or '未填写'}",
        f"- 分析编号：{analysis.get('analysis_id')}",
        f"- 分析状态：{_safe_text(analysis.get('status'))}",
    ]


def _product_lines(report_input: dict[str, Any]) -> list[str]:
    products = _record_list(report_input.get("products"))
    if not products:
        return ["- 本次分析没有可用产品清单。"]
    lines = [
        "| 产品ID | 中文名 | 英文名 | 品类 | 材质 | 认证 | 成本(CNY) | 重量(kg) | MOQ |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for product in products:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(product.get("id")),
                    _cell(product.get("product_name_cn")),
                    _cell(product.get("product_name_en")),
                    _cell(product.get("category")),
                    _cell(product.get("material")),
                    _cell(product.get("certification")),
                    _cell(product.get("cost_price_cny")),
                    _cell(product.get("weight_kg")),
                    _cell(product.get("moq")),
                ]
            )
            + " |"
        )
    intake_lines = _intake_source_lines(products)
    if intake_lines:
        lines.append("")
        lines.extend(intake_lines)
    product_profiles = _record_list(report_input.get("product_profiles"))
    if product_profiles:
        lines.append("")
        lines.append("- 关键词与 HS 编码来自产品理解节点，仅作为后续市场与内容检索输入。")
        for profile in product_profiles[:8]:
            lines.append(
                f"- 产品 {_safe_text(profile.get('id'))}：关键词 {_safe_text(profile.get('keyword')) or '未生成'}；"
                f"HS 编码 {_safe_text(profile.get('hs_code')) or '未生成'}。"
            )
    return lines


def _source_lines(report_input: dict[str, Any]) -> list[str]:
    sources = _record_list(report_input.get("data_sources"))
    lines = [
        "- 本报告区分公开 API、缓存、样本数据与 CSV fallback；fallback 表示演示兜底或证据不完整，不表示流程失败。",
        "- eBay、Rakuten、Reddit 若未出现在本次来源记录中，不作为本报告真实调用来源。",
    ]
    if _has_intake_source(report_input):
        lines.extend(INTAKE_SOURCE_BOUNDARY_LINES)
    if not sources:
        lines.append("- 本次分析没有可展示的数据源记录。")
        return lines
    lines.extend(
        [
            "| Provider | 来源标签 | 类型 | API 调用 | fallback | 说明 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for source in sources[:30]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(source.get("provider")),
                    _cell(source.get("label") or source.get("source_label")),
                    _cell(source.get("source_type")),
                    _cell("是" if source.get("api_invoked") else "否"),
                    _cell("是" if source.get("fallback_used") else "否"),
                    _cell(source.get("detail")),
                ]
            )
            + " |"
        )
    return lines


def _market_profile_lines(report_input: dict[str, Any]) -> list[str]:
    profiles = _record_list(report_input.get("market_profiles"))
    if not profiles:
        return ["- 本次 workflow_state 未保存目标国家市场概览。"]
    lines = [
        "| 国家 | 产品ID | 市场摘要 | 市场规模分 | 贸易分 | 物流分 | 竞争水平 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for profile in profiles[:20]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(profile.get("country")),
                    _cell(profile.get("product_id")),
                    _cell(profile.get("summary")),
                    _cell(profile.get("market_size_score")),
                    _cell(profile.get("trade_score")),
                    _cell(profile.get("logistics_score")),
                    _cell(profile.get("competition_level")),
                ]
            )
            + " |"
        )
    return lines


def _score_ranking_lines(report_input: dict[str, Any]) -> list[str]:
    scores = _record_list(report_input.get("scores"))
    if not scores:
        return ["- 本次分析没有可用机会评分。"]
    lines = [
        "| 排名 | 产品 | 国家 | 总分 | 趋势 | 价格 | 市场 | 供应 | 物流 | 内容 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for score in scores[:30]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(score.get("rank")),
                    _cell(score.get("product_name")),
                    _cell(score.get("country")),
                    _cell(score.get("total_score")),
                    _cell(score.get("trend_score")),
                    _cell(score.get("price_score")),
                    _cell(score.get("market_score")),
                    _cell(score.get("supply_score")),
                    _cell(score.get("logistics_score")),
                    _cell(score.get("content_score")),
                ]
            )
            + " |"
        )
    return lines


def _price_range_lines(report_input: dict[str, Any]) -> list[str]:
    ranges = _record_list((report_input.get("dashboard") or {}).get("price_ranges"))
    if not ranges:
        ranges = [
            {
                "product_name": score.get("product_name"),
                "country": score.get("country"),
                **(score.get("competitor_analysis") or {}),
            }
            for score in _record_list(report_input.get("scores"))
            if isinstance(score.get("competitor_analysis"), dict)
        ]
    if not ranges:
        return ["- 本次分析没有可用竞品价格区间。"]
    lines = [
        "| 产品 | 国家 | 关键词 | 最低价 | 中位价 | 平均价 | 最高价 | 币种 | 样本数 | 竞争水平 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in ranges[:30]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(item.get("product_name")),
                    _cell(item.get("country")),
                    _cell(item.get("keyword")),
                    _cell(item.get("min_price")),
                    _cell(item.get("median_price")),
                    _cell(item.get("avg_price")),
                    _cell(item.get("max_price")),
                    _cell(item.get("currency")),
                    _cell(item.get("item_count")),
                    _cell(item.get("competition_level")),
                ]
            )
            + " |"
        )
    lines.append("- 以上价格仅来自公开 API 或 CSV fallback 样本的区间信号，不代表平台实际成交表现。")
    return lines


def _content_trend_lines(report_input: dict[str, Any]) -> list[str]:
    trends = _record_list(report_input.get("content_trends"))
    if not trends:
        return ["- 本次 workflow_state 未保存内容趋势分析。"]
    lines: list[str] = []
    for trend in trends[:20]:
        lines.append(
            f"- 产品 {_safe_text(trend.get('product_id'))} / {_safe_text(trend.get('country'))} / "
            f"{_safe_text(trend.get('keyword')) or '未记录关键词'}：来源样本数 {_safe_text(trend.get('source_item_count')) or '0'}。"
        )
        lines.extend(_prefixed_list("  - 内容主题", trend.get("content_themes")))
        lines.extend(_prefixed_list("  - 营销角度", trend.get("marketing_angles")))
        lines.extend(_prefixed_list("  - 用户痛点", trend.get("pain_points")))
    return lines


def _recommendation_lines(report_input: dict[str, Any]) -> list[str]:
    recommendations = _record_list((report_input.get("dashboard") or {}).get("top_recommendations"))
    if not recommendations:
        recommendations = _record_list(report_input.get("scores"))[:5]
    if not recommendations:
        return ["- 本次分析没有生成推荐产品。"]
    lines: list[str] = []
    for item in recommendations[:8]:
        product_name = item.get("product_name") or item.get("product_name_en") or item.get("product_name_cn")
        lines.append(
            f"- #{_safe_text(item.get('rank')) or '-'} {_safe_text(product_name)} / {_safe_text(item.get('country'))}："
            f"机会分 {_safe_text(item.get('total_score')) or '未记录'}。"
        )
        if _safe_text(item.get("reason")):
            lines.append(f"  - 推荐理由：{_safe_text(item.get('reason'))}")
        if _safe_text(item.get("next_action")):
            lines.append(f"  - 建议动作：{_safe_text(item.get('next_action'))}")
    return lines


def _pricing_lines(report_input: dict[str, Any]) -> list[str]:
    scores = _record_list(report_input.get("scores"))
    lines: list[str] = []
    for score in scores[:12]:
        competitor = score.get("competitor_analysis") if isinstance(score.get("competitor_analysis"), dict) else {}
        suggestion = _safe_text(competitor.get("price_suggestion"))
        if suggestion:
            lines.append(
                f"- {_safe_text(score.get('product_name'))} / {_safe_text(score.get('country'))}：{suggestion}"
            )
    if not lines:
        return ["- 暂无可用定价建议。建议先复核竞品价格带、物流成本和平台费用后再设定试销价。"]
    lines.append("- 定价建议仅用于测试区间设计，正式发布前需复核实时平台价格、物流费用和合规成本。")
    return lines


def _marketing_listing_lines(report_input: dict[str, Any]) -> list[str]:
    assets = [_normalized_marketing_asset(item) for item in _record_list(report_input.get("marketing_assets"))]
    assets = [item for item in assets if item]
    if not assets:
        return ["- 暂无营销生成素材。可在营销生成页面基于推荐产品补齐英文标题与五点描述。"]
    lines: list[str] = []
    for asset in assets[:6]:
        lines.append(f"- 产品 {_safe_text(asset.get('product'))} / {_safe_text(asset.get('country'))}")
        lines.append(f"  - English title: {_safe_text(asset.get('title')) or '未生成'}")
        bullets = [item for item in asset.get("bullet_points", []) if isinstance(item, str)]
        if bullets:
            for index, bullet in enumerate(bullets[:5], start=1):
                lines.append(f"  - Bullet {index}: {_safe_text(bullet)}")
        else:
            lines.append("  - Five bullet points: 未生成")
    return lines


def _social_content_lines(report_input: dict[str, Any]) -> list[str]:
    assets = [_normalized_marketing_asset(item) for item in _record_list(report_input.get("marketing_assets"))]
    assets = [item for item in assets if item]
    if not assets:
        return ["- 暂无短视频与社媒内容建议。"]
    lines: list[str] = []
    for asset in assets[:6]:
        lines.append(f"- 产品 {_safe_text(asset.get('product'))} / {_safe_text(asset.get('country'))}")
        if _safe_text(asset.get("short_video_script")):
            lines.append(f"  - 短视频脚本：{_safe_text(asset.get('short_video_script'))}")
        social_posts = [item for item in asset.get("social_posts", []) if isinstance(item, str)]
        if social_posts:
            lines.extend(f"  - 社媒文案：{_safe_text(post)}" for post in social_posts[:3])
        keywords = [item for item in asset.get("pinterest_keywords", []) if isinstance(item, str)]
        if keywords:
            lines.append(f"  - 图片/社媒关键词：{_join_values(keywords)}")
    return lines


def _risk_lines(report_input: dict[str, Any]) -> list[str]:
    cards = _record_list((report_input.get("dashboard") or {}).get("risk_cards"))
    scores = _record_list(report_input.get("scores"))
    lines = [
        "- 本报告不是法律、税务、关务、认证或投资建议；正式上线前需由业务、法务和平台运营复核。",
        "- 公开 API、缓存、样本数据和 CSV fallback 均可能存在覆盖不足，适合用于方向判断和比赛 Demo 展示。",
    ]
    for card in cards[:10]:
        lines.append(
            f"- {_safe_text(card.get('severity')) or 'medium'}：{_safe_text(card.get('title'))} - {_safe_text(card.get('message'))}"
        )
    for score in scores[:10]:
        risk = _safe_text(score.get("risk"))
        if risk:
            lines.append(f"- {_safe_text(score.get('product_name'))} / {_safe_text(score.get('country'))}：{risk}")
        if score.get("fallback_used") or score.get("ai_fallback_used"):
            lines.append(
                f"- {_safe_text(score.get('product_name'))} / {_safe_text(score.get('country'))}：包含数据或 AI fallback，需复核实时证据。"
            )
    return _dedupe_lines(lines)


def _next_action_lines(report_input: dict[str, Any]) -> list[str]:
    scores = _record_list(report_input.get("scores"))
    actions: list[str] = []
    for score in scores[:10]:
        action = _safe_text(score.get("next_action"))
        if action:
            actions.append(f"- {_safe_text(score.get('product_name'))} / {_safe_text(score.get('country'))}：{action}")
    if actions:
        actions.append("- 汇总首轮测试结果后，更新评分、价格区间、内容主题和报告版本。")
        return _dedupe_lines(actions)
    return [
        "- 选择最高机会分的产品-国家组合，补齐实时平台样本和物流成本。",
        "- 用保守声明发布小规模 listing 和内容测试。",
        "- 根据点击、询盘、收藏、加购等运营信号复核下一轮选品。",
    ]


def _has_intake_source(report_input: dict[str, Any]) -> bool:
    products = _record_list(report_input.get("products"))
    return any(isinstance(product.get("intake_source"), dict) for product in products)


def _intake_source_lines(products: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for product in products:
        intake_source = product.get("intake_source")
        if not isinstance(intake_source, dict):
            continue
        product_name = _display_product_name(product)
        note = _safe_text(intake_source.get("confirmation_note")) or INTAKE_CONFIRMATION_NOTE
        platform = _safe_text(intake_source.get("source_platform")) or "unknown"
        confidence = _safe_text(intake_source.get("confidence_score")) or "未记录"
        source_url = _safe_text(intake_source.get("source_url"))
        domestic_price = _safe_text(intake_source.get("domestic_reference_price_cny"))
        pricing_note = _safe_text(intake_source.get("pricing_boundary_note"))
        lines.append(f"- {product_name}：{note} 来源平台 {platform}，AI 识别置信度 {confidence}。")
        if source_url:
            lines.append(f"  - 脱敏来源链接：{source_url}")
        if domestic_price:
            lines.append(f"  - 国内平台参考价：¥{domestic_price} CNY，仅用于产品信息完整度判断，不代表海外销售价格。")
        if pricing_note:
            lines.append(f"  - 价格边界：{pricing_note}")
        evidence = _record_list(intake_source.get("evidence"))
        if evidence:
            evidence_text = []
            for item in evidence[:3]:
                field = _safe_text(item.get("field"))
                source = _safe_text(item.get("source"))
                value = _safe_text(item.get("value"))
                if value:
                    evidence_text.append(f"{field or 'field'} / {source or 'source'}: {value}")
            if evidence_text:
                lines.append(f"  - 证据摘录：{_join_values(evidence_text)}")
    return lines


def _ensure_intake_source_markdown(markdown: str, report_input: dict[str, Any]) -> str:
    products = _record_list(report_input.get("products"))
    if not _has_intake_source(report_input):
        return markdown
    required_lines = [*INTAKE_SOURCE_BOUNDARY_LINES, *_intake_source_lines(products)]
    missing_lines = [line for line in required_lines if line not in markdown]
    if not missing_lines:
        return markdown
    return markdown.rstrip() + "\n\n### 智能导入来源与数据边界\n" + "\n".join(missing_lines)


def _fallback_notice(markdown: str) -> str:
    return (
        markdown
        + "\n\n---\n"
        + "生成说明：qwen3.6-plus 未返回可用的合规结构化报告，本版本使用后端确定性模板基于结构化数据生成。"
    )


def _compact_report_input(report_input: dict[str, Any]) -> dict[str, Any]:
    dashboard = report_input.get("dashboard") if isinstance(report_input.get("dashboard"), dict) else {}
    scores = _record_list(report_input.get("scores"))
    top_scores = [_compact_score(score) for score in scores[:8]]
    risk_cards = _record_list(dashboard.get("risk_cards"))
    score_risks = [
        {
            "product": _safe_text(score.get("product_name")),
            "country": _safe_text(score.get("country")),
            "risk": _safe_text(score.get("risk")),
            "next_action": _safe_text(score.get("next_action")),
            "fallback_used": bool(score.get("fallback_used") or score.get("ai_fallback_used")),
        }
        for score in scores[:8]
        if _safe_text(score.get("risk")) or _safe_text(score.get("next_action"))
    ]
    return _jsonable(
        {
            "report_title": report_input.get("report_title"),
            "analysis": report_input.get("analysis"),
            "company": report_input.get("company"),
            "products": [_compact_product(product) for product in _record_list(report_input.get("products"))[:8]],
            "top_scores": top_scores,
            "core_data_sources": _record_list(report_input.get("data_sources"))[:16],
            "market_profiles": [
                {
                    "product_id": item.get("product_id"),
                    "country": item.get("country"),
                    "summary": _safe_text(item.get("summary")),
                    "competition_level": _safe_text(item.get("competition_level")),
                }
                for item in _record_list(report_input.get("market_profiles"))[:8]
            ],
            "marketing_assets": [
                _compact_marketing_asset(asset)
                for asset in _record_list(report_input.get("marketing_assets"))[:8]
            ],
            "price_ranges": _record_list(dashboard.get("price_ranges"))[:8],
            "content_themes": _record_list(dashboard.get("content_themes"))[:12],
            "risks": {
                "cards": risk_cards[:8],
                "score_risks": score_risks,
            },
            "policy": report_input.get("policy"),
        }
    )


def _compact_product(product: dict[str, Any]) -> dict[str, Any]:
    intake_source = product.get("intake_source") if isinstance(product.get("intake_source"), dict) else None
    compact: dict[str, Any] = {
        "id": product.get("id"),
        "product_name_cn": product.get("product_name_cn"),
        "product_name_en": product.get("product_name_en"),
        "category": product.get("category"),
        "material": product.get("material"),
        "certification": product.get("certification"),
        "product_keywords": product.get("product_keywords"),
    }
    if intake_source is not None:
        compact["intake_source"] = {
            "source_type": intake_source.get("source_type"),
            "source_platform": intake_source.get("source_platform"),
            "confidence_score": intake_source.get("confidence_score"),
            "low_confidence": intake_source.get("low_confidence"),
            "confirmation_note": intake_source.get("confirmation_note"),
            "domestic_price_role": intake_source.get("domestic_price_role"),
        }
    return compact


def _compact_score(score: dict[str, Any]) -> dict[str, Any]:
    competitor = score.get("competitor_analysis") if isinstance(score.get("competitor_analysis"), dict) else {}
    evidence = score.get("evidence") if isinstance(score.get("evidence"), dict) else {}
    return {
        "rank": score.get("rank"),
        "product_id": score.get("product_id"),
        "product_name": score.get("product_name"),
        "country": score.get("country"),
        "total_score": score.get("total_score"),
        "dimensions": {
            "trend": score.get("trend_score"),
            "price": score.get("price_score"),
            "market": score.get("market_score"),
            "supply": score.get("supply_score"),
            "logistics": score.get("logistics_score"),
            "content": score.get("content_score"),
        },
        "reason": score.get("reason"),
        "risk": score.get("risk"),
        "next_action": score.get("next_action"),
        "fallback_used": bool(score.get("fallback_used") or score.get("ai_fallback_used")),
        "keyword": evidence.get("keyword"),
        "price_suggestion": competitor.get("price_suggestion"),
        "competition_level": competitor.get("competition_level"),
    }


def _compact_marketing_asset(asset: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalized_marketing_asset(asset)
    return {
        "product": normalized.get("product"),
        "country": normalized.get("country"),
        "title": normalized.get("title"),
        "bullet_points": normalized.get("bullet_points", [])[:5],
        "short_video_script": normalized.get("short_video_script"),
        "pinterest_keywords": normalized.get("pinterest_keywords", [])[:8],
        "risk_notes": asset.get("risk_notes", [])[:5] if isinstance(asset.get("risk_notes"), list) else [],
        "platform_listing_advice": asset.get("platform_listing_advice"),
    }


def _normalize_ai_markdown(content: str) -> str:
    content = content.strip()
    if not content.startswith(f"# {REPORT_TITLE}"):
        content = f"# {REPORT_TITLE}\n\n{content}"
    return content


def _validate_report_markdown(content: str) -> None:
    if REPORT_TITLE not in content:
        raise ValueError("Report title is missing.")
    for index, section_title in enumerate(REPORT_SECTION_TITLES, start=1):
        if f"## {index}. {section_title}" not in content:
            raise ValueError(f"Report section missing: {section_title}")
    lowered = content.casefold()
    for claim in FORBIDDEN_REPORT_CLAIMS:
        if claim.casefold() in lowered:
            raise ValueError(f"Forbidden report claim detected: {claim}")


def _normalized_marketing_asset(asset: dict[str, Any]) -> dict[str, Any]:
    title = asset.get("title") or asset.get("listing_title")
    bullet_points = asset.get("bullet_points") if isinstance(asset.get("bullet_points"), list) else []
    social_posts = asset.get("social_posts") if isinstance(asset.get("social_posts"), list) else []
    pinterest_keywords = asset.get("pinterest_keywords") if isinstance(asset.get("pinterest_keywords"), list) else []
    product = asset.get("product") or asset.get("product_name") or asset.get("product_id")
    return {
        "product": product,
        "country": asset.get("country"),
        "title": title,
        "bullet_points": bullet_points,
        "short_video_script": asset.get("short_video_script") or asset.get("ad_copy"),
        "social_posts": social_posts,
        "pinterest_keywords": pinterest_keywords or asset.get("seo_keywords") or [],
    }


def _products_by_id(
    db: Session,
    analysis_run: AnalysisRun,
    score_rows: list[OpportunityScore],
) -> dict[int, Product]:
    product_ids = {_optional_int(row.product_id) for row in score_rows}
    product_ids.update(_optional_int(item.get("id")) for item in analysis_run.input_products or [] if isinstance(item, dict))
    product_ids.discard(None)
    if not product_ids:
        return {}
    return {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    }


def _product_payload(product: Product | None, snapshot: dict[str, Any] | None, db: Session | None = None) -> dict[str, Any]:
    if product is not None:
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
                "product_keywords": snapshot.get("product_keywords") if snapshot else [],
                "intake_source": (snapshot.get("intake_source") if snapshot else None) or (_intake_source_for_product(db, product) if db is not None else None),
            }
        )
    return dict(snapshot or {})


def _score_payload(
    row: OpportunityScore,
    product: Product | None,
    snapshot: dict[str, Any] | None,
    db: Session | None = None,
) -> dict[str, Any]:
    product_data = _product_payload(product, snapshot, db)
    name = _display_product_name(product_data)
    return _jsonable(
        {
            "id": row.id,
            "analysis_id": row.analysis_id,
            "product_id": row.product_id,
            "product_name": name,
            "product_name_cn": product_data.get("product_name_cn"),
            "product_name_en": product_data.get("product_name_en"),
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
            "confirmation_note": INTAKE_CONFIRMATION_NOTE,
            "domestic_reference_price_cny": draft.price_cny,
            "domestic_price_role": "domestic_reference_only",
            "pricing_boundary_note": (
                "国内商品截图/链接价格仅用于判断产品信息完整度，不作为海外竞品价格、海外销售价格或采购成本。"
            ),
        }
    )


def _safe_url(value: str | None) -> str | None:
    text = _safe_text(value)
    if not text:
        return None
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return text[:300]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))[:300]


def _collect_sources(
    analysis_run: AnalysisRun,
    state: dict[str, Any],
    score_rows: list[OpportunityScore],
    dashboard: dict[str, Any],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    sources.extend(_record_list(dashboard.get("data_sources_used")))
    sources.extend(_record_list(state.get("provider_sources")))
    for row in score_rows:
        sources.extend(_record_list(row.sources))
    for log in analysis_run.step_logs or []:
        if isinstance(log, dict):
            sources.extend(_record_list(log.get("sources")))
    for breakdown in _record_list(state.get("provider_breakdown")):
        provider = _safe_text(breakdown.get("provider"))
        for label in breakdown.get("labels") or [provider]:
            sources.append(
                {
                    "provider": provider,
                    "label": label,
                    "source_type": ", ".join(str(item) for item in breakdown.get("source_types") or []),
                    "fallback_used": bool(breakdown.get("fallback_used")),
                    "api_invoked": bool(breakdown.get("api_invoked")),
                    "detail": "Aggregated provider summary from workflow state.",
                }
            )
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source in sources:
        provider = _safe_text(source.get("provider"))
        label = _safe_text(source.get("label") or source.get("source_label"))
        source_type = _safe_text(source.get("source_type")) or "unknown"
        if not provider:
            continue
        key = (provider, label, source_type)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = {
                "provider": provider,
                "label": label or provider,
                "source_type": source_type,
                "fallback_used": bool(source.get("fallback_used")),
                "api_invoked": bool(source.get("api_invoked")),
                "detail": _safe_text(source.get("detail")),
            }
        else:
            existing["fallback_used"] = bool(existing["fallback_used"] or source.get("fallback_used"))
            existing["api_invoked"] = bool(existing["api_invoked"] or source.get("api_invoked"))
            existing["detail"] = existing.get("detail") or _safe_text(source.get("detail"))
    return sorted(deduped.values(), key=lambda item: (item["provider"], item["label"], item["source_type"]))


def _product_snapshots_by_id(values: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        product_id = _optional_int(item.get("id"))
        if product_id is not None:
            snapshots[product_id] = item
    return snapshots


def _display_product_name(product: dict[str, Any]) -> str:
    cn = _safe_text(product.get("product_name_cn"))
    en = _safe_text(product.get("product_name_en"))
    if cn and en:
        return f"{cn} / {en}"
    return en or cn or "未命名产品"


def _prefixed_list(prefix: str, values: object) -> list[str]:
    cleaned = [_safe_text(value) for value in values] if isinstance(values, list) else []
    cleaned = [value for value in cleaned if value]
    if not cleaned:
        return []
    return [f"{prefix}：{value}" for value in cleaned[:8]]


def _record_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    for claim in FORBIDDEN_REPORT_CLAIMS:
        text = re.sub(re.escape(claim), "保守表述", text, flags=re.IGNORECASE)
    return text


def _join_values(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return "、".join(_safe_text(value) for value in values if _safe_text(value))


def _cell(value: object) -> str:
    text = _safe_text(value) or "-"
    return text.replace("|", "\\|")


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _jsonable(value: Any) -> Any:
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


def _is_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    cleaned = line.replace("|", "").replace(":", "").replace("-", "").strip()
    return cleaned == ""
