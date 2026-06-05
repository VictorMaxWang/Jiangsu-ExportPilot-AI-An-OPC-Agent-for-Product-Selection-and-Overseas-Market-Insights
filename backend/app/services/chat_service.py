from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AnalysisRun,
    ChatMessage,
    ChatSession,
    Company,
    OpportunityScore,
    Product,
    ProductKeyword,
    Report,
    ReportEditProposal,
)
from app.schemas import ChatMessageCreate, ChatSessionCreate
from app.services.ai import BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_global_chat_messages
from app.services.dashboard_service import DashboardService
from app.services.reports import render_report_html
from app.utils.redaction import redact_mapping, redact_text


MAX_PAGE_CONTEXT_CHARS = 1600
MAX_REPORT_EXCERPT_CHARS = 4200
MAX_REPORT_OUTPUT_CHARS = 20000
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CONTENT_CHARS = 1200
MAX_CONTEXT_VALUE_CHARS = 900
MAX_CONTEXT_JSON_CHARS = 14000
SECRET_LIKE_TEXT_RE = re.compile(r"(?i)\b(?:secret|token|apikey|api[_-]?key)[A-Za-z0-9_.:-]{4,}\b")


class ChatServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ChatNotFoundError(ChatServiceError):
    pass


class ChatInputError(ChatServiceError):
    pass


@dataclass(frozen=True)
class ChatSendOutcome:
    session: ChatSession
    user_message: ChatMessage
    assistant_message: ChatMessage
    proposal: ReportEditProposal | None = None


class ChatService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_session(self, payload: ChatSessionCreate) -> ChatSession:
        resolved = self._resolve_requested_context(
            company_id=payload.company_id,
            product_id=payload.product_id,
            analysis_id=payload.analysis_id,
            report_id=payload.report_id,
        )
        context_refs = _merge_context_refs(
            payload.context_refs,
            page_context=payload.page_context,
            ids=resolved,
        )
        session = ChatSession(
            title=payload.title or _default_title(payload.current_page, resolved),
            current_page=payload.current_page,
            company_id=resolved["company_id"],
            product_id=resolved["product_id"],
            analysis_id=resolved["analysis_id"],
            report_id=resolved["report_id"],
            context_refs=context_refs,
            safety_status="safe",
            status="active",
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def list_sessions(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        report_id: int | None = None,
        analysis_id: int | None = None,
        product_id: int | None = None,
        status: str | None = None,
    ) -> tuple[list[ChatSession], int]:
        statement = select(ChatSession)
        count_statement = select(func.count()).select_from(ChatSession)
        filters = []
        if report_id is not None:
            filters.append(ChatSession.report_id == report_id)
        if analysis_id is not None:
            filters.append(ChatSession.analysis_id == analysis_id)
        if product_id is not None:
            filters.append(ChatSession.product_id == product_id)
        if status is not None:
            filters.append(ChatSession.status == status)
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)
        statement = statement.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).offset(skip).limit(limit)
        return list(self._db.scalars(statement)), int(self._db.scalar(count_statement) or 0)

    async def send_message(self, session_id: int, payload: ChatMessageCreate, ai_client: Any) -> ChatSendOutcome:
        session = self._get_session_or_raise(session_id)
        if payload.role != "user":
            raise ChatInputError("CHAT_USER_MESSAGE_REQUIRED", "Chat message endpoint accepts user messages only.")

        self._apply_message_context(session, payload)
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=_safe_text(payload.content, MAX_REPORT_OUTPUT_CHARS),
            content_redacted=True,
            context_refs=_merge_context_refs(
                payload.context_refs,
                page_context=payload.page_context,
                ids={
                    "company_id": session.company_id,
                    "product_id": session.product_id,
                    "analysis_id": session.analysis_id,
                    "report_id": session.report_id,
                },
            ),
            safety_status="safe",
        )
        self._db.add(user_message)
        self._db.flush()

        assistant_message: ChatMessage
        proposal: ReportEditProposal | None = None
        try:
            prompt_payload = self._build_prompt_payload(session, user_message)
            result = await ai_client.chat(
                build_global_chat_messages(prompt_payload),
                temperature=0.35,
                max_tokens=1800,
                json_mode=True,
            )
            parsed = _parse_ai_payload(result.content)
            assistant_content = _assistant_content(parsed, result.content)
            intent = _safe_text_value(parsed.get("intent")) or _infer_intent(user_message.content)
            proposal = self._create_report_proposal_if_needed(
                session=session,
                user_message=user_message,
                parsed=parsed,
                assistant_content=assistant_content,
                intent=intent,
            )
            assistant_refs: dict[str, Any] = {
                "intent": intent,
                "context_budget": prompt_payload.get("context_budget"),
            }
            if proposal is not None:
                assistant_refs["proposal_id"] = proposal.id
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                content_redacted=True,
                context_refs=_sanitize_mapping(assistant_refs),
                safety_status="safe",
                model_used=result.model,
                token_count=_total_tokens(result.usage),
                report_edit_proposal_id=proposal.id if proposal is not None else None,
            )
        except BailianError as exc:
            assistant_message = self._degraded_assistant_message(session, exc, ai_client=ai_client)

        self._db.add(assistant_message)
        session.last_message_at = _utc_now()
        self._db.commit()
        self._db.refresh(session)
        self._db.refresh(user_message)
        self._db.refresh(assistant_message)
        if proposal is not None:
            self._db.refresh(proposal)
        return ChatSendOutcome(session, user_message, assistant_message, proposal)

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        self._get_session_or_raise(session_id)
        return list(
            self._db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            )
        )

    def _get_session_or_raise(self, session_id: int) -> ChatSession:
        session = self._db.get(ChatSession, session_id)
        if session is None:
            raise ChatNotFoundError("CHAT_SESSION_NOT_FOUND", "Chat session not found.")
        return session

    def _apply_message_context(self, session: ChatSession, payload: ChatMessageCreate) -> None:
        if payload.current_page is not None:
            session.current_page = payload.current_page
        requested = self._resolve_requested_context(
            company_id=payload.company_id if payload.company_id is not None else session.company_id,
            product_id=payload.product_id if payload.product_id is not None else session.product_id,
            analysis_id=payload.analysis_id if payload.analysis_id is not None else session.analysis_id,
            report_id=payload.report_id if payload.report_id is not None else session.report_id,
        )
        session.company_id = requested["company_id"]
        session.product_id = requested["product_id"]
        session.analysis_id = requested["analysis_id"]
        session.report_id = requested["report_id"]
        if payload.context_refs is not None or payload.page_context is not None:
            session.context_refs = _merge_context_refs(
                session.context_refs,
                payload.context_refs,
                page_context=payload.page_context,
                ids=requested,
            )

    def _resolve_requested_context(
        self,
        *,
        company_id: int | None,
        product_id: int | None,
        analysis_id: int | None,
        report_id: int | None,
    ) -> dict[str, int | None]:
        report = self._get_optional(Report, report_id, "REPORT_NOT_FOUND", "Report not found.")
        if report is not None:
            if analysis_id is not None and report.analysis_id != analysis_id:
                raise ChatInputError("CHAT_CONTEXT_MISMATCH", "Report does not belong to the requested analysis.")
            if company_id is not None and report.company_id != company_id:
                raise ChatInputError("CHAT_CONTEXT_MISMATCH", "Report does not belong to the requested company.")
            analysis_id = report.analysis_id
            company_id = report.company_id

        analysis = self._get_optional(AnalysisRun, analysis_id, "ANALYSIS_NOT_FOUND", "Analysis run not found.")
        if analysis is not None:
            if company_id is not None and analysis.company_id != company_id:
                raise ChatInputError("CHAT_CONTEXT_MISMATCH", "Analysis run does not belong to the requested company.")
            company_id = analysis.company_id

        product = self._get_optional(Product, product_id, "PRODUCT_NOT_FOUND", "Product not found.")
        if product is not None:
            if company_id is not None and product.company_id != company_id:
                raise ChatInputError("CHAT_CONTEXT_MISMATCH", "Product does not belong to the requested company.")
            if analysis is not None and product.company_id != analysis.company_id:
                raise ChatInputError("CHAT_CONTEXT_MISMATCH", "Product and analysis belong to different companies.")
            company_id = product.company_id

        self._get_optional(Company, company_id, "COMPANY_NOT_FOUND", "Company not found.")
        return {
            "company_id": company_id,
            "product_id": product_id,
            "analysis_id": analysis_id,
            "report_id": report_id,
        }

    def _get_optional(self, model: Any, item_id: int | None, code: str, message: str) -> Any | None:
        if item_id is None:
            return None
        item = self._db.get(model, item_id)
        if item is None:
            raise ChatNotFoundError(code, message)
        return item

    def _build_prompt_payload(self, session: ChatSession, user_message: ChatMessage) -> dict[str, Any]:
        report_context = self._report_context(session.report_id)
        context = {
            "session": {
                "id": session.id,
                "current_page": session.current_page,
                "company_id": session.company_id,
                "product_id": session.product_id,
                "analysis_id": session.analysis_id,
                "report_id": session.report_id,
                "page_context": _page_context(session.context_refs),
            },
            "company": self._company_context(session.company_id),
            "product": self._product_context(session.product_id),
            "analysis": self._analysis_context(session.analysis_id),
            "report": report_context,
        }
        prompt_context, truncated = _trim_context_payload(_sanitize_mapping(context), MAX_CONTEXT_JSON_CHARS)
        field_truncated = isinstance(report_context, dict) and bool(report_context.get("content_truncated"))
        return {
            "user_question": user_message.content,
            "recent_messages": self._recent_history(session.id),
            "context": prompt_context,
            "context_budget": {
                "max_context_json_chars": MAX_CONTEXT_JSON_CHARS,
                "max_report_excerpt_chars": MAX_REPORT_EXCERPT_CHARS,
                "context_truncated": bool(truncated or field_truncated),
            },
            "output_contract": "Return only the JSON object specified by the system prompt.",
        }

    def _company_context(self, company_id: int | None) -> dict[str, Any] | None:
        company = self._db.get(Company, company_id) if company_id is not None else None
        if company is None:
            return None
        return {
            "id": company.id,
            "name": _safe_text_value(company.name),
            "region": _safe_text_value(company.region),
            "industry": _safe_text_value(company.industry),
            "description": _safe_text(company.description, MAX_CONTEXT_VALUE_CHARS),
            "target_countries": company.target_countries or [],
        }

    def _product_context(self, product_id: int | None) -> dict[str, Any] | None:
        product = self._db.get(Product, product_id) if product_id is not None else None
        if product is None:
            return None
        keywords = list(
            self._db.scalars(
                select(ProductKeyword)
                .where(ProductKeyword.product_id == product.id)
                .order_by(ProductKeyword.created_at.desc(), ProductKeyword.id.desc())
                .limit(10)
            )
        )
        return {
            "id": product.id,
            "company_id": product.company_id,
            "product_name_cn": _safe_text_value(product.product_name_cn),
            "product_name_en": _safe_text_value(product.product_name_en),
            "category": _safe_text_value(product.category),
            "material": _safe_text_value(product.material),
            "certification": _safe_text_value(product.certification),
            "moq": product.moq,
            "cost_price_cny": _jsonable(product.cost_price_cny),
            "weight_kg": _jsonable(product.weight_kg),
            "package_size": _safe_text_value(product.package_size),
            "description": _safe_text(product.description, MAX_CONTEXT_VALUE_CHARS),
            "keywords": [
                {
                    "keyword": _safe_text_value(keyword.keyword),
                    "language": _safe_text_value(keyword.language),
                    "country": _safe_text_value(keyword.country),
                    "source": _safe_text_value(keyword.source),
                }
                for keyword in keywords
            ],
        }

    def _analysis_context(self, analysis_id: int | None) -> dict[str, Any] | None:
        analysis = self._db.get(AnalysisRun, analysis_id) if analysis_id is not None else None
        if analysis is None:
            return None
        rows = list(
            self._db.scalars(
                select(OpportunityScore)
                .where(OpportunityScore.analysis_id == analysis.id)
                .order_by(OpportunityScore.rank.asc(), OpportunityScore.total_score.desc())
                .limit(8)
            )
        )
        dashboard = DashboardService(self._db).get_dashboard(analysis.id)
        dashboard_payload = dashboard.model_dump(mode="json") if dashboard is not None else {}
        return {
            "id": analysis.id,
            "company_id": analysis.company_id,
            "status": _safe_text_value(analysis.status),
            "current_step": _safe_text_value(analysis.current_step),
            "target_countries": analysis.target_countries or [],
            "started_at": _jsonable(analysis.started_at),
            "finished_at": _jsonable(analysis.finished_at),
            "input_products": _compact_records(analysis.input_products or [], 8),
            "top_scores": [_score_context(row) for row in rows],
            "dashboard": {
                "top_recommendations": _compact_records(dashboard_payload.get("top_recommendations"), 5),
                "risk_cards": _compact_records(dashboard_payload.get("risk_cards"), 6),
                "data_sources_used": _compact_records(dashboard_payload.get("data_sources_used"), 10),
                "price_ranges": _compact_records(dashboard_payload.get("price_ranges"), 6),
                "content_themes": _compact_records(dashboard_payload.get("content_themes"), 8),
            },
            "step_logs": _compact_step_logs(analysis.step_logs or []),
            "workflow_state_summary": _workflow_state_summary(analysis.workflow_state or {}),
        }

    def _report_context(self, report_id: int | None) -> dict[str, Any] | None:
        report = self._db.get(Report, report_id) if report_id is not None else None
        if report is None:
            return None
        markdown = _current_report_markdown(report)
        excerpt, truncated = _trim_text_with_tail(markdown, MAX_REPORT_EXCERPT_CHARS)
        return {
            "id": report.id,
            "analysis_id": report.analysis_id,
            "company_id": report.company_id,
            "title": _safe_text_value(report.title),
            "current_version_id": report.current_version_id,
            "content_excerpt_markdown": excerpt,
            "content_char_count": len(markdown),
            "content_truncated": truncated,
            "proposal_rule": "Chat may create report_edit_proposals only; it must not overwrite reports or versions.",
        }

    def _recent_history(self, session_id: int) -> list[dict[str, Any]]:
        messages = list(
            self._db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .limit(MAX_HISTORY_MESSAGES)
            )
        )
        return [
            {
                "role": message.role,
                "content": _safe_text(message.content, MAX_HISTORY_CONTENT_CHARS),
                "proposal_id": message.report_edit_proposal_id,
            }
            for message in reversed(messages)
        ]

    def _create_report_proposal_if_needed(
        self,
        *,
        session: ChatSession,
        user_message: ChatMessage,
        parsed: dict[str, Any],
        assistant_content: str,
        intent: str,
    ) -> ReportEditProposal | None:
        if session.report_id is None:
            return None
        should_create = intent == "report_edit_proposal" or _looks_like_report_edit(user_message.content)
        if not should_create:
            return None
        report = self._db.get(Report, session.report_id)
        if report is None:
            return None
        proposal_payload = parsed.get("proposal")
        proposal_data = proposal_payload if isinstance(proposal_payload, dict) else {}
        proposed_markdown = _optional_limited_text(proposal_data.get("proposed_markdown"), MAX_REPORT_OUTPUT_CHARS)
        proposed_html = _optional_limited_text(proposal_data.get("proposed_html"), MAX_REPORT_OUTPUT_CHARS)
        if proposed_markdown and not proposed_html:
            proposed_html = render_report_html(proposed_markdown)
        diff = _optional_dict(proposal_data.get("diff")) or {
            "summary": _safe_text(assistant_content, MAX_CONTEXT_VALUE_CHARS),
            "changes": [],
            "proposal_only": True,
        }
        replacement_blocks = _optional_dict_list(proposal_data.get("replacement_blocks"))
        risk_notes = _optional_string_list(proposal_data.get("risk_notes")) or [
            "Proposal requires human review before creating a new report version.",
        ]
        evidence = _optional_dict_list(proposal_data.get("evidence")) or [
            {
                "source": "report",
                "detail": f"report_id={report.id}, current_version_id={report.current_version_id}",
            }
        ]
        proposal = ReportEditProposal(
            report_id=report.id,
            target_version_id=report.current_version_id,
            source_chat_session_id=session.id,
            user_intent=_optional_limited_text(proposal_data.get("user_intent"), 4000) or user_message.content,
            proposed_markdown=proposed_markdown,
            proposed_html=proposed_html,
            diff=_sanitize_mapping(diff),
            replacement_blocks=_sanitize_mapping(replacement_blocks),
            risk_notes=_optional_string_list(_sanitize_mapping(risk_notes)),
            evidence=_optional_dict_list(_sanitize_mapping(evidence)),
            confidence_score=_confidence_score(proposal_data.get("confidence_score")),
            status="draft",
        )
        self._db.add(proposal)
        self._db.flush()
        return proposal

    def _degraded_assistant_message(self, session: ChatSession, exc: BailianError, *, ai_client: Any) -> ChatMessage:
        error_message = f"{getattr(exc, 'code', 'BAILIAN_ERROR')}: backend AI request failed safely."
        return ChatMessage(
            session_id=session.id,
            role="assistant",
            content=(
                "聊天暂时无法调用 qwen3.6-plus，已保留你的问题。"
                "请稍后重试，或先根据页面中的结构化分析、看板和报告内容继续判断。"
            ),
            content_redacted=True,
            context_refs={"intent": "other", "degraded": True},
            safety_status="degraded",
            model_used=str(getattr(ai_client, "model_name", "") or "") or None,
            error_code=getattr(exc, "code", "BAILIAN_ERROR"),
            error_message=error_message,
        )


def _default_title(current_page: str | None, ids: dict[str, int | None]) -> str:
    if ids.get("report_id") is not None:
        return f"Report chat #{ids['report_id']}"
    if ids.get("analysis_id") is not None:
        return f"Analysis chat #{ids['analysis_id']}"
    if ids.get("product_id") is not None:
        return f"Product chat #{ids['product_id']}"
    return f"{current_page or 'Global'} chat"


def _merge_context_refs(
    *refs: dict[str, Any] | None,
    page_context: dict[str, Any] | None = None,
    ids: dict[str, int | None] | None = None,
) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    for item in refs:
        if isinstance(item, dict):
            merged.update(item)
    if page_context is not None:
        merged["page_context"] = _limited_mapping(page_context, MAX_PAGE_CONTEXT_CHARS)
    if ids:
        merged["context_ids"] = {key: value for key, value in ids.items() if value is not None}
    return _sanitize_mapping(merged) if merged else None


def _page_context(context_refs: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(context_refs, dict):
        return None
    value = context_refs.get("page_context")
    return value if isinstance(value, dict) else None


def _limited_mapping(value: dict[str, Any], limit: int) -> dict[str, Any]:
    cleaned = _sanitize_mapping(value)
    text = _jsonable(cleaned)
    serialized = str(text)
    if len(serialized) <= limit:
        return cleaned if isinstance(cleaned, dict) else {}
    return {"summary": _safe_text(serialized, limit), "truncated": True}


def _parse_ai_payload(content: str) -> dict[str, Any]:
    try:
        parsed = parse_json_object(content)
    except AiJsonParseError:
        return {"assistant_message": content, "intent": "other", "proposal": None}
    return parsed


def _assistant_content(parsed: dict[str, Any], raw_content: str) -> str:
    value = parsed.get("assistant_message")
    if isinstance(value, str) and value.strip():
        return _safe_text(value, MAX_REPORT_OUTPUT_CHARS)
    return _safe_text(raw_content, MAX_REPORT_OUTPUT_CHARS)


def _infer_intent(content: str) -> str:
    if _looks_like_report_edit(content):
        return "report_edit_proposal"
    normalized = content.casefold()
    if any(term in normalized for term in ("risk", "风险", "隐患")):
        return "product_risk"
    if any(term in normalized for term in ("答辩", "talk track", "presentation", "defense")):
        return "defense_talk_track"
    if any(term in normalized for term in ("推荐", "recommend", "score", "评分")):
        return "explain_recommendation"
    if any(term in normalized for term in ("报告", "report")):
        return "explain_report"
    return "other"


def _looks_like_report_edit(content: str) -> bool:
    normalized = content.casefold()
    terms = (
        "修改",
        "改写",
        "调整",
        "优化",
        "补充",
        "删除",
        "替换",
        "润色",
        "rewrite",
        "revise",
        "edit",
        "change the report",
        "update the report",
        "improve the report",
        "polish the report",
    )
    return any(term in normalized for term in terms) and any(term in normalized for term in ("报告", "report"))


def _score_context(row: OpportunityScore) -> dict[str, Any]:
    return {
        "id": row.id,
        "product_id": row.product_id,
        "country": _safe_text_value(row.country),
        "rank": row.rank,
        "total_score": _jsonable(row.total_score),
        "dimensions": {
            "trend_score": _jsonable(row.trend_score),
            "price_score": _jsonable(row.price_score),
            "market_score": _jsonable(row.market_score),
            "supply_score": _jsonable(row.supply_score),
            "logistics_score": _jsonable(row.logistics_score),
            "content_score": _jsonable(row.content_score),
        },
        "reason": _safe_text(row.reason, MAX_CONTEXT_VALUE_CHARS),
        "risk": _safe_text(row.risk, MAX_CONTEXT_VALUE_CHARS),
        "next_action": _safe_text(row.next_action, MAX_CONTEXT_VALUE_CHARS),
        "fallback_used": row.fallback_used,
        "ai_fallback_used": row.ai_fallback_used,
        "sources": _compact_records(row.sources or [], 5),
        "evidence": _compact_mapping(row.evidence or {}, MAX_CONTEXT_VALUE_CHARS),
        "competitor_analysis": _compact_mapping(row.competitor_analysis or {}, MAX_CONTEXT_VALUE_CHARS),
    }


def _compact_step_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for log in logs[:8]:
        if not isinstance(log, dict):
            continue
        records.append(
            {
                "step_id": _safe_text_value(log.get("step_id")),
                "title": _safe_text_value(log.get("title")),
                "status": _safe_text_value(log.get("status")),
                "fallback_used": bool(log.get("fallback_used")),
                "error_code": _safe_text_value(log.get("error_code")),
                "sources": _compact_records(log.get("sources"), 3),
            }
        )
    return records


def _workflow_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_sources": _compact_records(state.get("provider_sources"), 8),
        "provider_breakdown": _compact_records(state.get("provider_breakdown"), 8),
        "market_profiles": _compact_records(state.get("market_profiles"), 5),
        "content_trends": _compact_records(state.get("content_trends"), 5),
        "marketing_assets": _compact_records(state.get("marketing_assets"), 4),
    }


def _compact_records(value: object, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    records: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            records.append(_compact_mapping(item, MAX_CONTEXT_VALUE_CHARS))
        if len(records) >= limit:
            break
    return records


def _compact_mapping(value: dict[str, Any], text_limit: int) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, str):
            compact[str(key)] = _safe_text(item, text_limit)
        elif isinstance(item, dict):
            compact[str(key)] = _compact_mapping(item, max(120, text_limit // 2))
        elif isinstance(item, list):
            compact[str(key)] = [
                _compact_mapping(entry, max(120, text_limit // 2)) if isinstance(entry, dict) else _jsonable(entry)
                for entry in item[:8]
            ]
        else:
            compact[str(key)] = _jsonable(item)
    return _sanitize_mapping(compact)


def _current_report_markdown(report: Report) -> str:
    if report.current_version is not None and report.current_version.content_markdown:
        return report.current_version.content_markdown
    return report.content_markdown or ""


def _trim_context_payload(context: dict[str, Any], limit: int) -> tuple[dict[str, Any], bool]:
    serialized = str(_jsonable(context))
    if len(serialized) <= limit:
        return context, False
    trimmed = dict(context)
    report = trimmed.get("report")
    if isinstance(report, dict) and isinstance(report.get("content_excerpt_markdown"), str):
        excerpt, _ = _trim_text_with_tail(report["content_excerpt_markdown"], 1800)
        report["content_excerpt_markdown"] = excerpt
        report["content_truncated"] = True
    serialized = str(_jsonable(trimmed))
    if len(serialized) <= limit:
        return trimmed, True
    return {
        "session": trimmed.get("session"),
        "company": trimmed.get("company"),
        "product": trimmed.get("product"),
        "analysis": _compact_mapping(trimmed.get("analysis"), 500) if isinstance(trimmed.get("analysis"), dict) else None,
        "report": _compact_mapping(trimmed.get("report"), 900) if isinstance(trimmed.get("report"), dict) else None,
        "truncated": True,
    }, True


def _trim_text_with_tail(value: str | None, limit: int) -> tuple[str, bool]:
    text = _safe_text(value, limit * 2)
    if len(text) <= limit:
        return text, False
    head = max(1, int(limit * 0.65))
    tail = max(1, limit - head - 32)
    return f"{text[:head].rstrip()}\n\n[...context trimmed...]\n\n{text[-tail:].lstrip()}", True


def _safe_text(value: object, limit: int) -> str:
    text = redact_text(str(value or "")) or ""
    text = SECRET_LIKE_TEXT_RE.sub("[REDACTED]", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + " [truncated]"


def _safe_text_value(value: object) -> str | None:
    if value is None:
        return None
    text = _safe_text(value, MAX_CONTEXT_VALUE_CHARS)
    return text or None


def _optional_limited_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = _safe_text(value, limit)
    return text or None


def _optional_dict(value: object) -> dict[str, Any] | None:
    return _sanitize_mapping(value) if isinstance(value, dict) else None


def _optional_dict_list(value: object) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    items = [_sanitize_mapping(item) for item in value if isinstance(item, dict)]
    return items or None


def _optional_string_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [_safe_text(item, MAX_CONTEXT_VALUE_CHARS) for item in value if _safe_text(item, MAX_CONTEXT_VALUE_CHARS)]
    return items or None


def _confidence_score(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if score < Decimal("0") or score > Decimal("1"):
        return None
    return score.quantize(Decimal("0.0001"))


def _total_tokens(usage: dict[str, Any] | None) -> int | None:
    if not isinstance(usage, dict):
        return None
    value = usage.get("total_tokens")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _sanitize_mapping(value: Any) -> Any:
    return redact_mapping(_jsonable(value))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
