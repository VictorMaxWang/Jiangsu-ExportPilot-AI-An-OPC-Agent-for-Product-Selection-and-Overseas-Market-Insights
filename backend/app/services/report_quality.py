from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, OpportunityScore, Report


QualityIssue = dict[str, str]

DATA_SOURCE_TERMS = (
    "source",
    "sources",
    "data source",
    "data sources",
    "evidence",
    "provider",
    "world bank",
    "gdelt",
    "youtube",
    "etsy",
    "un comtrade",
    "csv",
    "数据源",
    "数据来源",
    "来源",
    "证据",
    "供应商",
)

FALLBACK_TERMS = (
    "fallback",
    "csv fallback",
    "sample",
    "sample data",
    "directional",
    "incomplete",
    "limitation",
    "limitations",
    "样本",
    "兜底",
    "回退",
    "不完整",
    "限制",
    "局限",
)

NEGATION_TERMS = (
    "not",
    "no ",
    "do not",
    "does not",
    "cannot",
    "should not",
    "without",
    "unsupported",
    "avoid",
    "avoids",
    "not represent",
    "not a",
    "不",
    "不得",
    "不能",
    "不可",
    "不代表",
    "不等于",
    "不应",
    "未经",
)

CLAIM_PATTERNS = (
    ("GMV_CLAIM", re.compile(r"\bGMV\b|平台交易额|成交额", re.IGNORECASE), "GMV or transaction-value claim needs verified source support."),
    ("REAL_SALES_CLAIM", re.compile(r"真实销量|实际销量|real sales|verified sales|sales volume", re.IGNORECASE), "Real-sales claims are not supported by marketplace samples."),
    ("GUARANTEED_SALES", re.compile(r"保证销量|保证销售|guaranteed sales|sales guarantee", re.IGNORECASE), "Guaranteed sales claims are prohibited."),
    ("GUARANTEED_CONVERSION", re.compile(r"保证转化|guaranteed conversion|conversion guarantee", re.IGNORECASE), "Guaranteed conversion claims are prohibited."),
    ("FORECAST_CLAIM", re.compile(r"销量预测|销售预测|利润预测|sales forecast|sales prediction|profit forecast|gmv forecast", re.IGNORECASE), "Forecast claims must be removed or reframed as directional analysis."),
    ("BESTSELLER_CLAIM", re.compile(r"爆款|畅销第一|销量第一|best-?selling|bestseller|no\.?\s*1", re.IGNORECASE), "Bestseller or ranking claims require verified evidence and are blocked here."),
)

EXAGGERATED_TERMS = (
    "guaranteed",
    "100%",
    "best",
    "爆款",
    "必然",
    "稳赚",
    "保证",
)


def assess_report_markdown(
    markdown: str | None,
    *,
    fallback_expected: bool = False,
) -> dict[str, Any]:
    text = (markdown or "").strip()
    normalized = text.casefold()
    issues: list[QualityIssue] = []

    has_data_source_note = any(term.casefold() in normalized for term in DATA_SOURCE_TERMS)
    has_fallback_disclosure = any(term.casefold() in normalized for term in FALLBACK_TERMS)
    has_caveat = any(
        term in normalized
        for term in (
            "limitation",
            "limitations",
            "directional",
            "human review",
            "manual review",
            "not represent",
            "不代表",
            "需复核",
            "人工复核",
            "局限",
            "限制",
        )
    )

    if not text:
        issues.append(_issue("MISSING_DRAFT", "blocker", "Proposal markdown draft is required before creating a version."))
    if not has_data_source_note:
        issues.append(_issue("MISSING_DATA_SOURCE_NOTE", "blocker", "Draft must state data sources or evidence basis."))
    if fallback_expected and not has_fallback_disclosure:
        issues.append(_issue("MISSING_FALLBACK_DISCLOSURE", "blocker", "Draft must disclose fallback, sample, or incomplete evidence when fallback data was used."))
    if not has_caveat:
        issues.append(_issue("MISSING_CAVEAT", "warning", "Draft should include a caveat near claims that rely on directional or incomplete evidence."))

    for code, pattern, message in CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            if not _is_negated_context(text, match.start(), match.end()):
                issues.append(_issue(code, "blocker", message))
                break

    if any(term.casefold() in normalized for term in EXAGGERATED_TERMS):
        issues.append(_issue("EXAGGERATED_LANGUAGE_REVIEW", "warning", "Draft contains strong language; confirm it is caveated and evidence-backed."))

    status = "blocked" if any(issue["severity"] == "blocker" for issue in issues) else ("warning" if issues else "pass")
    return {
        "status": status,
        "checks": {
            "has_data_source_note": has_data_source_note,
            "fallback_expected": fallback_expected,
            "has_fallback_disclosure": has_fallback_disclosure,
            "has_caveat": has_caveat,
        },
        "issues": issues,
    }


def report_fallback_expected(db: Session, report: Report) -> bool:
    analysis = db.get(AnalysisRun, report.analysis_id)
    if analysis is None:
        return False
    if _records_have_fallback(analysis.step_logs):
        return True
    state = analysis.workflow_state if isinstance(analysis.workflow_state, dict) else {}
    if _records_have_fallback(state.get("provider_sources")) or _records_have_fallback(state.get("provider_breakdown")):
        return True
    return bool(
        db.scalar(
            select(OpportunityScore.id)
            .where(
                OpportunityScore.analysis_id == analysis.id,
                (OpportunityScore.fallback_used.is_(True)) | (OpportunityScore.ai_fallback_used.is_(True)),
            )
            .limit(1)
        )
    )


def quality_issue_messages(quality: dict[str, Any]) -> list[str]:
    issues = quality.get("issues") if isinstance(quality, dict) else None
    if not isinstance(issues, list):
        return []
    messages: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity") or "warning")
        message = str(issue.get("message") or "").strip()
        if message:
            messages.append(f"{severity}: {message}")
    return messages


def _records_have_fallback(value: object) -> bool:
    if isinstance(value, dict):
        if bool(value.get("fallback_used") or value.get("ai_fallback_used")):
            return True
        return any(_records_have_fallback(item) for item in value.values())
    if isinstance(value, list):
        return any(_records_have_fallback(item) for item in value)
    return False


def _is_negated_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 60) : min(len(text), end + 60)].casefold()
    return any(term.casefold() in window for term in NEGATION_TERMS)


def _issue(code: str, severity: str, message: str) -> QualityIssue:
    return {"code": code, "severity": severity, "message": message}
