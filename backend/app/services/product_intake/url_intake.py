from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Company, DomesticProductLink, ProductDraft, ProductImportJob
from app.schemas.product_intake import (
    AiResultType,
    ProductDraftRead,
    ProductUrlIntakeResponse,
    QwenProductUnderstandingResponse,
)
from app.services.ai import BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_url_product_understanding_messages
from app.services.product_intake.domestic_page_fetcher import (
    DomesticPageFetchInput,
    DomesticPageFetchResult,
    fetch_domestic_product_page,
)
from app.services.product_intake.domestic_url_parser import DomesticUrlParseResult, parse_domestic_product_url
from app.services.product_intake.screenshot_analyzer import ProductIntakeRequestError, sanitize_intake_text


SCREENSHOT_MESSAGE = "请上传截图继续分析"
LOW_CONFIDENCE_THRESHOLD = Decimal("0.65")
MIN_IDENTIFIED_CONFIDENCE = Decimal("0.35")
SECURITY_PARSE_STATUSES = {
    "invalid_url": ("INVALID_URL", "URL was not valid."),
    "invalid_scheme": ("URL_UNSUPPORTED_SCHEME", "Only http and https URLs are allowed."),
    "blocked_host": ("URL_SECURITY_BLOCKED", "URL target is not allowed."),
    "unsupported_domain": ("URL_HOST_NOT_ALLOWED", "URL host is not supported."),
}


async def analyze_url_intake(
    db: Session,
    *,
    company_id: int,
    url: str,
    client: BailianClient,
    settings: Settings | None = None,
) -> ProductUrlIntakeResponse:
    settings = settings or get_settings()
    if db.get(Company, company_id) is None:
        raise ProductIntakeRequestError(404, "COMPANY_NOT_FOUND", "Company not found")

    parsed_url = parse_domestic_product_url(url)
    if parsed_url.parse_status in SECURITY_PARSE_STATUSES:
        code, message = SECURITY_PARSE_STATUSES[parsed_url.parse_status]
        raise ProductIntakeRequestError(422, code, message)

    job, link = _create_url_job_and_link(db, company_id=company_id, parsed_url=parsed_url)

    if parsed_url.parse_status != "parsed":
        draft = _create_blank_draft(
            db,
            job,
            link,
            code="URL_PARSE_FAILED",
            message=SCREENSHOT_MESSAGE,
        )
        return _build_url_response(
            job,
            draft,
            status="needs_screenshot",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="manual_required",
            ai_fallback_used=False,
        )

    if not settings.enable_domestic_url_fetch:
        draft = _create_blank_draft(
            db,
            job,
            link,
            code="DOMESTIC_URL_FETCH_DISABLED",
            message=SCREENSHOT_MESSAGE,
        )
        return _build_url_response(
            job,
            draft,
            status="needs_screenshot",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="manual_required",
            ai_fallback_used=False,
        )

    fetch_result = await fetch_domestic_product_page(
        DomesticPageFetchInput(
            platform=parsed_url.platform,
            original_url=parsed_url.original_url,
            normalized_url=parsed_url.normalized_url,
            item_id=parsed_url.item_id or None,
            sku_id=parsed_url.sku_id or None,
        )
    )
    _update_link_from_fetch_result(db, job, link, fetch_result)
    if fetch_result.parse_status != "parsed":
        draft = _create_blank_draft(
            db,
            job,
            link,
            code=fetch_result.error_code or "URL_PARSE_FAILED",
            message=SCREENSHOT_MESSAGE,
        )
        return _build_url_response(
            job,
            draft,
            status="needs_screenshot",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="manual_required",
            ai_fallback_used=False,
        )

    try:
        completion = await _call_qwen_for_url(client, parsed_url, fetch_result)
    except BailianError as exc:
        draft = _create_blank_draft(
            db,
            job,
            link,
            code=exc.code,
            message=SCREENSHOT_MESSAGE,
        )
        return _build_url_response(
            job,
            draft,
            status="failed",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="fallback",
            ai_fallback_used=True,
        )

    job.model_used = completion.model
    try:
        understanding = QwenProductUnderstandingResponse.model_validate(parse_json_object(completion.content))
    except AiJsonParseError:
        draft = _create_blank_draft(
            db,
            job,
            link,
            code="AI_RESPONSE_PARSE_ERROR",
            message=SCREENSHOT_MESSAGE,
            model_used=completion.model,
        )
        return _build_url_response(
            job,
            draft,
            status="failed",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="fallback",
            ai_fallback_used=True,
        )
    except ValidationError:
        draft = _create_blank_draft(
            db,
            job,
            link,
            code="AI_RESPONSE_SCHEMA_ERROR",
            message=SCREENSHOT_MESSAGE,
            model_used=completion.model,
        )
        return _build_url_response(
            job,
            draft,
            status="failed",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="fallback",
            ai_fallback_used=True,
        )

    if _requires_screenshot(understanding):
        draft = _create_blank_draft(
            db,
            job,
            link,
            code="AI_PRODUCT_NOT_IDENTIFIED",
            message=SCREENSHOT_MESSAGE,
            model_used=completion.model,
        )
        return _build_url_response(
            job,
            draft,
            status="needs_screenshot",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="manual_required",
            ai_fallback_used=False,
        )

    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=understanding,
        source_platform=parsed_url.platform,
        source_url=parsed_url.normalized_url,
    )
    if understanding.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        job.status = "needs_screenshot"
        job.error_code = "LOW_CONFIDENCE"
        job.error_message = SCREENSHOT_MESSAGE
        db.commit()
        db.refresh(job)
        db.refresh(draft)
        return _build_url_response(
            job,
            draft,
            status="needs_screenshot",
            message=SCREENSHOT_MESSAGE,
            ai_result_type="manual_required",
            ai_fallback_used=False,
        )

    return _build_url_response(
        job,
        draft,
        status="draft_ready",
        message="draft_ready",
        ai_result_type="real_qwen",
        ai_fallback_used=False,
    )


def _create_url_job_and_link(
    db: Session,
    *,
    company_id: int,
    parsed_url: DomesticUrlParseResult,
) -> tuple[ProductImportJob, DomesticProductLink]:
    source_url = sanitize_intake_text(parsed_url.original_url, max_length=2048) or parsed_url.normalized_url
    job = ProductImportJob(
        company_id=company_id,
        source_type="url",
        source_platform=parsed_url.platform,
        source_url=source_url,
        status="processing",
    )
    link = DomesticProductLink(
        import_job=job,
        platform=parsed_url.platform,
        original_url=source_url,
        normalized_url=parsed_url.normalized_url or None,
        item_id=parsed_url.item_id or None,
        sku_id=parsed_url.sku_id or None,
        parse_status=parsed_url.parse_status,
    )
    db.add(job)
    db.add(link)
    db.commit()
    db.refresh(job)
    db.refresh(link)
    return job, link


def _update_link_from_fetch_result(
    db: Session,
    job: ProductImportJob,
    link: DomesticProductLink,
    fetch_result: DomesticPageFetchResult,
) -> None:
    parsed_title = fetch_result.og_title or fetch_result.title
    link.parsed_title = sanitize_intake_text(parsed_title, max_length=512)
    link.parsed_text = sanitize_intake_text(fetch_result.visible_text, max_length=6000)
    link.parse_status = fetch_result.parse_status
    link.parse_error = sanitize_intake_text(fetch_result.error_code, max_length=160)
    if fetch_result.parse_status == "parsed":
        job.raw_text = link.parsed_text
    db.commit()
    db.refresh(job)
    db.refresh(link)


async def _call_qwen_for_url(
    client: BailianClient,
    parsed_url: DomesticUrlParseResult,
    fetch_result: DomesticPageFetchResult,
):
    parsed_normalized = urlsplit(parsed_url.normalized_url)
    payload = {
        "task": "extract_product_draft_from_public_domestic_product_url_text",
        "url_context": {
            "platform": parsed_url.platform,
            "host": parsed_normalized.hostname or "",
            "path": parsed_normalized.path,
            "item_id": parsed_url.item_id,
            "sku_id": parsed_url.sku_id,
            "parse_status": parsed_url.parse_status,
        },
        "page_extract": {
            "title": fetch_result.title,
            "meta_description": fetch_result.meta_description,
            "og_title": fetch_result.og_title,
            "og_image_present": bool(fetch_result.og_image),
            "visible_text": fetch_result.visible_text[:6000],
            "price_text_candidates": fetch_result.price_candidates,
            "product_name_text_candidates": fetch_result.product_name_candidates,
        },
        "requirements": [
            "Return only the strict JSON object requested by the system prompt.",
            "Use null or [] when evidence is missing.",
            "Do not copy private buyer, account, order, address, phone, cookie, token, header, or secret content.",
            "If confidence is low, recommend screenshot upload in risk_notes.",
        ],
    }
    messages = build_url_product_understanding_messages(payload)
    return await client.chat(messages, temperature=0.2, max_tokens=1800, json_mode=True)


def _requires_screenshot(understanding: QwenProductUnderstandingResponse) -> bool:
    if not understanding.product_name_cn:
        return True
    return understanding.confidence_score < MIN_IDENTIFIED_CONFIDENCE


def _create_blank_draft(
    db: Session,
    job: ProductImportJob,
    link: DomesticProductLink,
    *,
    code: str,
    message: str,
    model_used: str | None = None,
) -> ProductDraft:
    if model_used:
        job.model_used = model_used
    safe_message = sanitize_intake_text(message, max_length=240) or SCREENSHOT_MESSAGE
    job.status = "needs_screenshot" if not code.startswith("AI_RESPONSE_") and not code.startswith("BAILIAN_") else "failed"
    job.error_code = code
    job.error_message = safe_message
    link.parse_status = "needs_screenshot" if link.parse_status != "parsed" else link.parse_status
    if link.parse_error is None:
        link.parse_error = sanitize_intake_text(code, max_length=160)
    draft = ProductDraft(
        import_job_id=job.id,
        company_id=job.company_id,
        source_platform=job.source_platform,
        source_url=link.normalized_url,
        confidence_score=Decimal("0.0000"),
        status="draft",
        selling_points={
            "selling_points_cn": [],
            "selling_points_en": [],
            "usage_scenarios": [],
            "cross_border_keywords_en": [],
            "risk_notes": [safe_message],
        },
        target_users=[],
        color_options=[],
        evidence=[],
    )
    db.add(draft)
    db.commit()
    db.refresh(job)
    db.refresh(link)
    db.refresh(draft)
    return draft


def _create_draft_from_understanding(
    db: Session,
    job: ProductImportJob,
    *,
    understanding: QwenProductUnderstandingResponse,
    source_platform: str,
    source_url: str,
) -> ProductDraft:
    confidence = understanding.confidence_score
    draft = ProductDraft(
        import_job_id=job.id,
        company_id=job.company_id,
        product_name_cn=understanding.product_name_cn,
        product_name_en=understanding.product_name_en,
        category=understanding.category,
        price_cny=understanding.price_cny,
        weight_kg=_parse_weight_kg(understanding.weight_estimate),
        package_size=_limit_text(understanding.dimensions, 128),
        material=_limit_text(understanding.material, 128),
        color_options=_sanitize_text_list(understanding.color_options),
        specification=_limit_text(understanding.specification, 4000),
        selling_points={
            "selling_points_cn": _sanitize_text_list(understanding.selling_points_cn),
            "selling_points_en": _sanitize_text_list(understanding.selling_points_en),
            "usage_scenarios": _sanitize_text_list(understanding.usage_scenarios),
            "cross_border_keywords_en": _sanitize_text_list(understanding.cross_border_keywords_en),
            "risk_notes": _sanitize_text_list(understanding.risk_notes),
        },
        target_users=_sanitize_text_list(understanding.target_users),
        source_platform=source_platform,
        source_url=source_url,
        evidence=_sanitize_evidence(understanding),
        confidence_score=confidence,
        status="draft",
    )
    job.source_platform = source_platform
    job.status = "draft_ready"
    job.error_code = None
    job.error_message = None
    db.add(draft)
    db.commit()
    db.refresh(job)
    db.refresh(draft)
    return draft


def _build_url_response(
    job: ProductImportJob,
    draft: ProductDraft,
    *,
    status: str,
    message: str,
    ai_result_type: AiResultType,
    ai_fallback_used: bool,
) -> ProductUrlIntakeResponse:
    return ProductUrlIntakeResponse(
        job_id=job.id,
        draft_id=draft.id,
        status=status,
        message=message,
        ai_result_type=ai_result_type,
        ai_fallback_used=ai_fallback_used,
        model_used=job.model_used,
        error_code=job.error_code,
        error_message=job.error_message,
        draft=ProductDraftRead.model_validate(draft),
    )


def _parse_weight_kg(value: str | None) -> Decimal | None:
    if not value:
        return None
    text = str(value).strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilogram|kilograms|千克|公斤|g|克)\b", text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    if match.group(2) in {"g", "克"}:
        amount = amount / Decimal("1000")
    return amount


def _sanitize_evidence(understanding: QwenProductUnderstandingResponse) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for item in understanding.evidence:
        source = item.source if item.source in {"url_text", "model_inference"} else "url_text"
        sanitized.append(
            {
                "field": sanitize_intake_text(item.field, max_length=128) or "unknown",
                "source": source,
                "value": sanitize_intake_text(item.value, max_length=180),
            }
        )
    return sanitized


def _sanitize_text_list(values: list[str]) -> list[str]:
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


def _limit_text(value: Any, max_length: int) -> str | None:
    return sanitize_intake_text(value, max_length=max_length)
