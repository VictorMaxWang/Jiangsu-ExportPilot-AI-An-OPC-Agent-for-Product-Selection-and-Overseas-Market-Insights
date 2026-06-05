from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Company, CompanyDraft
from app.schemas.companies import CompanyRead
from app.schemas.company_intake import (
    CompanyDraftListResponse,
    CompanyDraftRead,
    CompanyDraftRejectRequest,
    CompanyDraftUpdateRequest,
)
from app.services.company_intake.photo_analyzer import (
    CompanyIntakeRequestError,
    normalize_source_platform,
    normalize_target_countries,
    sanitize_company_intake_text,
    sanitize_credit_code_suffix,
    sanitize_text_list,
)


DRAFT_STATUS_DRAFT = "draft"
DRAFT_STATUS_CONFIRMED = "confirmed"
DRAFT_STATUS_REJECTED = "rejected"
INTAKE_CONFIRMATION_NOTE = "Company profile was created from user-uploaded company photos and confirmed by the user."


def list_company_drafts(
    db: Session,
    *,
    status: str | None,
    source_platform: str | None,
    limit: int,
    offset: int,
) -> CompanyDraftListResponse:
    filters = []
    if status is not None:
        filters.append(CompanyDraft.status == _clean_filter(status, max_length=32))
    if source_platform is not None:
        filters.append(CompanyDraft.import_job.has(source_platform=normalize_source_platform(source_platform)))

    count_statement = select(func.count()).select_from(CompanyDraft)
    statement = select(CompanyDraft).order_by(CompanyDraft.created_at.desc(), CompanyDraft.id.desc()).offset(offset).limit(limit)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    return CompanyDraftListResponse(
        items=[CompanyDraftRead.model_validate(draft) for draft in db.scalars(statement)],
        total=db.scalar(count_statement) or 0,
        limit=limit,
        offset=offset,
    )


def update_company_draft(
    db: Session,
    draft_id: int,
    payload: CompanyDraftUpdateRequest,
) -> CompanyDraftRead:
    draft = _get_draft_or_error(db, draft_id)
    _ensure_editable(draft)

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(draft, field, _sanitize_update_value(field, value))

    db.commit()
    db.refresh(draft)
    return CompanyDraftRead.model_validate(draft)


def confirm_company_draft(db: Session, draft_id: int) -> CompanyRead:
    try:
        draft = _get_draft_for_update(db, draft_id)
        _ensure_confirmable(draft)

        company_name = sanitize_company_intake_text(draft.company_name, max_length=255)
        if not company_name:
            raise CompanyIntakeRequestError(
                422,
                "DRAFT_CONFIRMATION_VALIDATION_FAILED",
                "Company name is required before confirming a company draft.",
            )

        company = Company(
            name=company_name,
            region=sanitize_company_intake_text(draft.region, max_length=128),
            industry=sanitize_company_intake_text(draft.industry, max_length=128),
            description=_build_company_description(draft),
            target_countries=normalize_target_countries(draft.target_countries),
        )
        db.add(company)
        db.flush()

        draft.status = DRAFT_STATUS_CONFIRMED
        draft.confirmed_company_id = company.id
        if draft.import_job is not None:
            draft.import_job.status = DRAFT_STATUS_CONFIRMED

        db.commit()
        db.refresh(company)
        return CompanyRead.model_validate(company)
    except CompanyIntakeRequestError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def reject_company_draft(
    db: Session,
    draft_id: int,
    payload: CompanyDraftRejectRequest,
) -> CompanyDraftRead:
    try:
        draft = _get_draft_for_update(db, draft_id)
        _ensure_rejectable(draft)

        reason = sanitize_company_intake_text(payload.reason, max_length=500)
        if reason:
            risk_notes = sanitize_text_list(draft.risk_notes)
            risk_notes.append(f"Reject reason: {reason}")
            draft.risk_notes = _dedupe_preserving_order(risk_notes)

        draft.status = DRAFT_STATUS_REJECTED
        draft.confirmed_company_id = None
        db.commit()
        db.refresh(draft)
        return CompanyDraftRead.model_validate(draft)
    except CompanyIntakeRequestError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _get_draft_or_error(db: Session, draft_id: int) -> CompanyDraft:
    draft = db.get(CompanyDraft, draft_id)
    if draft is None:
        raise CompanyIntakeRequestError(404, "DRAFT_NOT_FOUND", "Company draft not found")
    return draft


def _get_draft_for_update(db: Session, draft_id: int) -> CompanyDraft:
    statement = (
        select(CompanyDraft)
        .options(selectinload(CompanyDraft.import_job))
        .where(CompanyDraft.id == draft_id)
        .with_for_update()
    )
    draft = db.scalar(statement)
    if draft is None:
        raise CompanyIntakeRequestError(404, "DRAFT_NOT_FOUND", "Company draft not found")
    return draft


def _ensure_editable(draft: CompanyDraft) -> None:
    if draft.status != DRAFT_STATUS_DRAFT:
        raise CompanyIntakeRequestError(409, "DRAFT_NOT_EDITABLE", "Only draft company drafts can be edited")


def _ensure_confirmable(draft: CompanyDraft) -> None:
    if draft.status == DRAFT_STATUS_REJECTED:
        raise CompanyIntakeRequestError(409, "DRAFT_ALREADY_REJECTED", "Rejected company drafts cannot be confirmed")
    if draft.status == DRAFT_STATUS_CONFIRMED or draft.confirmed_company_id is not None:
        raise CompanyIntakeRequestError(409, "DRAFT_ALREADY_CONFIRMED", "Company draft has already been confirmed")
    if draft.status != DRAFT_STATUS_DRAFT:
        raise CompanyIntakeRequestError(409, "DRAFT_NOT_CONFIRMABLE", "Only draft company drafts can be confirmed")


def _ensure_rejectable(draft: CompanyDraft) -> None:
    if draft.status == DRAFT_STATUS_CONFIRMED or draft.confirmed_company_id is not None:
        raise CompanyIntakeRequestError(409, "DRAFT_ALREADY_CONFIRMED", "Confirmed company drafts cannot be rejected")
    if draft.status == DRAFT_STATUS_REJECTED:
        raise CompanyIntakeRequestError(409, "DRAFT_ALREADY_REJECTED", "Company draft has already been rejected")
    if draft.status != DRAFT_STATUS_DRAFT:
        raise CompanyIntakeRequestError(409, "DRAFT_NOT_REJECTABLE", "Only draft company drafts can be rejected")


def _sanitize_update_value(field: str, value: object) -> object:
    if field == "company_name":
        return sanitize_company_intake_text(value, max_length=255)
    if field == "credit_code_suffix":
        return sanitize_credit_code_suffix(value)
    if field in {"region", "industry", "contact_role"}:
        return sanitize_company_intake_text(value, max_length=128)
    if field == "website":
        return _safe_url(value)
    if field == "description":
        return sanitize_company_intake_text(value, max_length=4000)
    if field == "main_products":
        return sanitize_text_list(value)
    if field == "target_countries":
        return normalize_target_countries(value)
    if field == "risk_notes":
        return sanitize_text_list(value)
    if field == "evidence":
        return _sanitize_evidence_update(value)
    return value


def _clean_filter(value: str, *, max_length: int) -> str:
    return (sanitize_company_intake_text(value, max_length=max_length) or "").strip().lower()


def _safe_url(value: object) -> str | None:
    text = sanitize_company_intake_text(value, max_length=2048)
    if not text:
        return None
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return sanitize_company_intake_text(text, max_length=300)
    safe = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return sanitize_company_intake_text(safe, max_length=300)


def _sanitize_evidence_update(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []

    sanitized: list[dict[str, object]] = []
    for item in value[:80]:
        if not isinstance(item, dict):
            continue
        field = sanitize_company_intake_text(item.get("field"), max_length=128)
        source = sanitize_company_intake_text(item.get("source"), max_length=64)
        evidence_value = sanitize_company_intake_text(item.get("value"), max_length=180)
        if not field or not source:
            continue
        sanitized_item: dict[str, object] = {"field": field, "source": source, "value": evidence_value}
        image_index = item.get("image_index")
        if isinstance(image_index, int) and image_index >= 0:
            sanitized_item["image_index"] = image_index
        image_role = sanitize_company_intake_text(item.get("image_role"), max_length=64)
        if image_role:
            sanitized_item["image_role"] = image_role
        sanitized.append(sanitized_item)
    return sanitized


def _build_company_description(draft: CompanyDraft) -> str | None:
    sections: list[str] = [INTAKE_CONFIRMATION_NOTE]

    description = sanitize_company_intake_text(draft.description, max_length=4000)
    if description:
        sections.append(description)

    _append_list_section(sections, "Main products", sanitize_text_list(draft.main_products))

    website = _safe_url(draft.website)
    if website:
        sections.append(f"Website: {website}")

    contact_role = sanitize_company_intake_text(draft.contact_role, max_length=128)
    if contact_role:
        sections.append(f"Contact role: {contact_role}")

    if draft.credit_code_suffix:
        suffix = sanitize_credit_code_suffix(draft.credit_code_suffix)
        if suffix:
            sections.append(f"Unified social credit code suffix: {suffix}")

    if draft.confidence_score is not None:
        sections.append(f"AI confidence: {_format_decimal(draft.confidence_score)}")

    evidence_lines = _evidence_lines(draft.evidence)
    if evidence_lines:
        sections.append("Evidence excerpts:\n" + "\n".join(f"- {line}" for line in evidence_lines))

    _append_list_section(sections, "Risk notes", sanitize_text_list(draft.risk_notes))
    return "\n\n".join(sections) or None


def _append_list_section(sections: list[str], title: str, values: list[str]) -> None:
    cleaned = _dedupe_preserving_order(values)
    if cleaned:
        sections.append(f"{title}:\n" + "\n".join(f"- {value}" for value in cleaned))


def _evidence_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        field = sanitize_company_intake_text(item.get("field"), max_length=64)
        source = sanitize_company_intake_text(item.get("source"), max_length=64)
        evidence_value = sanitize_company_intake_text(item.get("value"), max_length=180)
        image_index = item.get("image_index")
        image_role = sanitize_company_intake_text(item.get("image_role"), max_length=64)
        image_context = None
        if isinstance(image_index, int):
            image_context = f"image_index={image_index}"
            if image_role:
                image_context = f"{image_context} image_role={image_role}"
        parts = [part for part in (field, source, image_context) if part]
        if evidence_value:
            lines.append(f"{' / '.join(parts) or 'unknown'}: {evidence_value}")
    return lines


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_company_intake_text(value, max_length=180)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
