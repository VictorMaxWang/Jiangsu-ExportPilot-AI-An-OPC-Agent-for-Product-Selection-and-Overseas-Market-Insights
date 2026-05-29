from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Product, ProductDraft, ProductKeyword
from app.schemas.product_intake import (
    ProductDraftConfirmRequest,
    ProductDraftListResponse,
    ProductDraftRead,
    ProductDraftRejectRequest,
    ProductDraftUpdateRequest,
)
from app.services.product_intake.screenshot_analyzer import ProductIntakeRequestError, sanitize_intake_text


DRAFT_STATUS_DRAFT = "draft"
DRAFT_STATUS_CONFIRMED = "confirmed"
DRAFT_STATUS_REJECTED = "rejected"
KEYWORD_SOURCE = "product_intake_confirmed"
INTAKE_CONFIRMATION_NOTE = "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。"
SELLING_POINT_KEYS = {
    "selling_points_cn",
    "selling_points_en",
    "usage_scenarios",
    "cross_border_keywords_en",
    "risk_notes",
}


def list_product_drafts(
    db: Session,
    *,
    company_id: int | None,
    status: str | None,
    source_platform: str | None,
    limit: int,
    offset: int,
) -> ProductDraftListResponse:
    filters = []
    if company_id is not None:
        filters.append(ProductDraft.company_id == company_id)
    if status is not None:
        filters.append(ProductDraft.status == _clean_filter(status, max_length=32))
    if source_platform is not None:
        filters.append(ProductDraft.source_platform == _clean_filter(source_platform, max_length=32))

    count_statement = select(func.count()).select_from(ProductDraft)
    statement = select(ProductDraft).order_by(ProductDraft.created_at.desc(), ProductDraft.id.desc()).offset(offset).limit(limit)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    return ProductDraftListResponse(
        items=[ProductDraftRead.model_validate(draft) for draft in db.scalars(statement)],
        total=db.scalar(count_statement) or 0,
        limit=limit,
        offset=offset,
    )


def update_product_draft(
    db: Session,
    draft_id: int,
    payload: ProductDraftUpdateRequest,
) -> ProductDraftRead:
    draft = _get_draft_or_error(db, draft_id)
    _ensure_editable(draft)

    data = payload.model_dump(exclude_unset=True)
    selling_points = _normalized_selling_points(draft.selling_points)
    for field, value in data.items():
        if field == "selling_points":
            selling_points = _merge_selling_points(selling_points, value)
            continue
        if field == "risk_notes":
            selling_points["risk_notes"] = _sanitize_text_list(value)
            continue
        setattr(draft, field, _sanitize_update_value(field, value))

    if "selling_points" in data or "risk_notes" in data:
        draft.selling_points = selling_points

    db.commit()
    db.refresh(draft)
    return ProductDraftRead.model_validate(draft)


def confirm_product_draft(
    db: Session,
    draft_id: int,
    payload: ProductDraftConfirmRequest,
) -> Product:
    try:
        draft = _get_draft_for_update(db, draft_id)
        _ensure_company_scope(draft, payload.company_id)
        _ensure_confirmable(draft)

        product_name_cn = sanitize_intake_text(draft.product_name_cn, max_length=255)
        if not product_name_cn:
            raise ProductIntakeRequestError(
                422,
                "DRAFT_CONFIRMATION_VALIDATION_FAILED",
                "Product name in Chinese is required before confirming a draft.",
            )

        product = Product(
            company_id=draft.company_id,
            product_name_cn=product_name_cn,
            product_name_en=sanitize_intake_text(draft.product_name_en, max_length=255),
            category=sanitize_intake_text(draft.category, max_length=128),
            cost_price_cny=draft.cost_price_cny,
            weight_kg=draft.weight_kg,
            package_size=sanitize_intake_text(draft.package_size, max_length=128),
            material=sanitize_intake_text(draft.material, max_length=128),
            description=_build_product_description(draft),
        )
        db.add(product)
        db.flush()

        _persist_intake_keywords(db, product, draft)
        draft.status = DRAFT_STATUS_CONFIRMED
        draft.confirmed_product_id = product.id
        if draft.import_job is not None:
            draft.import_job.status = DRAFT_STATUS_CONFIRMED

        db.commit()
        db.refresh(product)
        return product
    except ProductIntakeRequestError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def reject_product_draft(
    db: Session,
    draft_id: int,
    payload: ProductDraftRejectRequest,
) -> ProductDraftRead:
    try:
        draft = _get_draft_for_update(db, draft_id)
        _ensure_company_scope(draft, payload.company_id)
        _ensure_rejectable(draft)

        reason = sanitize_intake_text(payload.reason, max_length=500)
        if reason:
            selling_points = _normalized_selling_points(draft.selling_points)
            risk_notes = selling_points.get("risk_notes", [])
            risk_notes.append(f"拒绝原因：{reason}")
            selling_points["risk_notes"] = _dedupe_preserving_order(risk_notes)
            draft.selling_points = selling_points

        draft.status = DRAFT_STATUS_REJECTED
        draft.confirmed_product_id = None
        db.commit()
        db.refresh(draft)
        return ProductDraftRead.model_validate(draft)
    except ProductIntakeRequestError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _get_draft_or_error(db: Session, draft_id: int) -> ProductDraft:
    draft = db.get(ProductDraft, draft_id)
    if draft is None:
        raise ProductIntakeRequestError(404, "DRAFT_NOT_FOUND", "Product draft not found")
    return draft


def _get_draft_for_update(db: Session, draft_id: int) -> ProductDraft:
    statement = (
        select(ProductDraft)
        .options(selectinload(ProductDraft.import_job))
        .where(ProductDraft.id == draft_id)
        .with_for_update()
    )
    draft = db.scalar(statement)
    if draft is None:
        raise ProductIntakeRequestError(404, "DRAFT_NOT_FOUND", "Product draft not found")
    return draft


def _ensure_company_scope(draft: ProductDraft, company_id: int) -> None:
    if draft.company_id != company_id:
        raise ProductIntakeRequestError(404, "DRAFT_NOT_FOUND", "Product draft not found")


def _ensure_editable(draft: ProductDraft) -> None:
    if draft.status != DRAFT_STATUS_DRAFT:
        raise ProductIntakeRequestError(409, "DRAFT_NOT_EDITABLE", "Only draft product drafts can be edited")


def _ensure_confirmable(draft: ProductDraft) -> None:
    if draft.status == DRAFT_STATUS_REJECTED:
        raise ProductIntakeRequestError(409, "DRAFT_ALREADY_REJECTED", "Rejected product drafts cannot be confirmed")
    if draft.status == DRAFT_STATUS_CONFIRMED or draft.confirmed_product_id is not None:
        raise ProductIntakeRequestError(409, "DRAFT_ALREADY_CONFIRMED", "Product draft has already been confirmed")
    if draft.status != DRAFT_STATUS_DRAFT:
        raise ProductIntakeRequestError(409, "DRAFT_NOT_CONFIRMABLE", "Only draft product drafts can be confirmed")


def _ensure_rejectable(draft: ProductDraft) -> None:
    if draft.status == DRAFT_STATUS_CONFIRMED or draft.confirmed_product_id is not None:
        raise ProductIntakeRequestError(409, "DRAFT_ALREADY_CONFIRMED", "Confirmed product drafts cannot be rejected")
    if draft.status == DRAFT_STATUS_REJECTED:
        raise ProductIntakeRequestError(409, "DRAFT_ALREADY_REJECTED", "Product draft has already been rejected")
    if draft.status != DRAFT_STATUS_DRAFT:
        raise ProductIntakeRequestError(409, "DRAFT_NOT_REJECTABLE", "Only draft product drafts can be rejected")


def _sanitize_update_value(field: str, value: object) -> object:
    if field in {"product_name_cn", "product_name_en"}:
        return sanitize_intake_text(value, max_length=255)
    if field in {"category", "package_size", "material"}:
        return sanitize_intake_text(value, max_length=128)
    if field == "specification":
        return sanitize_intake_text(value, max_length=4000)
    if field in {"color_options", "target_users"}:
        return _sanitize_text_list(value)
    if field == "evidence":
        return _sanitize_evidence_update(value)
    return value


def _clean_filter(value: str, *, max_length: int) -> str:
    return (sanitize_intake_text(value, max_length=max_length) or "").strip().lower()


def _normalized_selling_points(value: object) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    if isinstance(value, dict):
        for key in SELLING_POINT_KEYS:
            normalized[key] = _sanitize_text_list(value.get(key))
    for key in SELLING_POINT_KEYS:
        normalized.setdefault(key, [])
    return normalized


def _merge_selling_points(
    current: dict[str, list[str]],
    updates: object,
) -> dict[str, list[str]]:
    if updates is None:
        return {key: [] for key in SELLING_POINT_KEYS}
    if not isinstance(updates, dict):
        return current
    merged = {key: list(values) for key, values in current.items()}
    for key, value in updates.items():
        if key in SELLING_POINT_KEYS:
            merged[key] = _sanitize_text_list(value)
    for key in SELLING_POINT_KEYS:
        merged.setdefault(key, [])
    return merged


def _sanitize_text_list(values: object) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_intake_text(value, max_length=180)
        if not text:
            continue
        dedupe_key = text.casefold()
        if dedupe_key in seen:
            continue
        cleaned.append(text)
        seen.add(dedupe_key)
    return cleaned


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_intake_text(value, max_length=180)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def _sanitize_evidence_update(value: object) -> list[dict[str, str | None]]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []

    sanitized: list[dict[str, str | None]] = []
    for item in value[:50]:
        if not isinstance(item, dict):
            continue
        field = sanitize_intake_text(item.get("field"), max_length=128)
        source = sanitize_intake_text(item.get("source"), max_length=64)
        evidence_value = sanitize_intake_text(item.get("value"), max_length=180)
        if not field or not source:
            continue
        sanitized.append({"field": field, "source": source, "value": evidence_value})
    return sanitized


def _build_product_description(draft: ProductDraft) -> str | None:
    sections: list[str] = [INTAKE_CONFIRMATION_NOTE]
    selling_points = _normalized_selling_points(draft.selling_points)

    specification = sanitize_intake_text(draft.specification, max_length=4000)
    if specification:
        sections.append(f"规格说明：{specification}")

    _append_list_section(sections, "核心卖点", selling_points["selling_points_cn"] + selling_points["selling_points_en"])
    _append_list_section(sections, "适用场景", selling_points["usage_scenarios"])
    _append_list_section(sections, "目标用户", _sanitize_text_list(draft.target_users))
    _append_list_section(sections, "跨境关键词建议", selling_points["cross_border_keywords_en"])

    if draft.price_cny is not None:
        sections.append(f"参考价格：¥{_format_decimal(draft.price_cny)} CNY（平台标价/截图或链接参考价，非成交价，非采购成本）")
        if draft.cost_price_cny is None:
            sections.append("成本备注：草稿未填写采购成本；参考价格仅作为人工估价线索，未写入采购成本。")

    source_lines = []
    source_platform = sanitize_intake_text(draft.source_platform, max_length=32)
    source_url = _safe_url(draft.source_url)
    if source_platform:
        source_lines.append(f"来源平台：{source_platform}")
    if source_url:
        source_lines.append(f"来源链接：{source_url}")
    if draft.confidence_score is not None:
        source_lines.append(f"AI 识别置信度：{_format_decimal(draft.confidence_score)}")
    if source_lines:
        sections.append("\n".join(source_lines))

    evidence_lines = _evidence_lines(draft.evidence)
    if evidence_lines:
        sections.append("证据摘录：\n" + "\n".join(f"- {line}" for line in evidence_lines))

    _append_list_section(sections, "风险备注", selling_points["risk_notes"])
    return "\n\n".join(sections) or None


def _append_list_section(sections: list[str], title: str, values: list[str]) -> None:
    cleaned = _dedupe_preserving_order(values)
    if cleaned:
        sections.append(f"{title}：\n" + "\n".join(f"- {value}" for value in cleaned))


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _safe_url(value: str | None) -> str | None:
    text = sanitize_intake_text(value, max_length=2048)
    if not text:
        return None
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return sanitize_intake_text(text, max_length=300)
    safe = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return sanitize_intake_text(safe, max_length=300)


def _evidence_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        field = sanitize_intake_text(item.get("field"), max_length=64)
        source = sanitize_intake_text(item.get("source"), max_length=64)
        evidence_value = sanitize_intake_text(item.get("value"), max_length=180)
        parts = [part for part in (field, source) if part]
        if evidence_value:
            lines.append(f"{' / '.join(parts) or 'unknown'}: {evidence_value}")
    return lines


def _persist_intake_keywords(db: Session, product: Product, draft: ProductDraft) -> None:
    existing = {
        ((keyword or "").casefold(), language or "", country or "")
        for keyword, language, country in db.execute(
            select(ProductKeyword.keyword, ProductKeyword.language, ProductKeyword.country).where(
                ProductKeyword.product_id == product.id
            )
        )
    }
    for keyword in _keyword_candidates(draft):
        dedupe_key = (keyword.casefold(), "en", "")
        if dedupe_key in existing:
            continue
        db.add(
            ProductKeyword(
                product_id=product.id,
                keyword=keyword,
                language="en",
                country=None,
                source=KEYWORD_SOURCE,
            )
        )
        existing.add(dedupe_key)


def _keyword_candidates(draft: ProductDraft) -> list[str]:
    selling_points = _normalized_selling_points(draft.selling_points)
    candidates = list(selling_points["cross_border_keywords_en"])
    product_name_en = sanitize_intake_text(draft.product_name_en, max_length=255)
    if product_name_en:
        candidates.append(product_name_en)

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        text = " ".join(value.split()).strip()[:255]
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned
