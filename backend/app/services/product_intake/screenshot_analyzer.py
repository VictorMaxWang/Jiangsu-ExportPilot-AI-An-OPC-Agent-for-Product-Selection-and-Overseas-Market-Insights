from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.models import Company, ProductDraft, ProductImportAsset, ProductImportJob
from app.schemas.product_intake import (
    ProductDraftSummary,
    ProductDraftRead,
    ProductImportAssetRead,
    ProductImportJobDetailResponse,
    ProductScreenshotIntakeResponse,
    QwenProductUnderstandingResponse,
)
from app.services.ai import BailianChatCompletion, BailianClient, BailianError
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_screenshot_product_understanding_messages
from app.utils.redaction import redact_text


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
FORMAT_TO_MIME_AND_EXT = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}
LOW_CONFIDENCE_THRESHOLD = Decimal("0.65")
MIN_IDENTIFIED_CONFIDENCE = Decimal("0.35")
Image.MAX_IMAGE_PIXELS = 50_000_000

_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")
_WINDOWS_PATH_RE = re.compile(r"(?i)[a-z]:\\[^\s]+")


class ProductIntakeRequestError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class StoredScreenshot:
    data: bytes
    file_name: str
    file_path: str
    resolved_path: Path
    mime_type: str
    file_size: int
    width: int
    height: int


async def analyze_screenshot_upload(
    db: Session,
    *,
    company_id: int,
    upload: UploadFile,
    source_platform: str | None,
    client: BailianClient,
    settings: Settings | None = None,
) -> ProductScreenshotIntakeResponse:
    settings = settings or get_settings()
    if db.get(Company, company_id) is None:
        raise ProductIntakeRequestError(404, "COMPANY_NOT_FOUND", "Company not found")

    normalized_platform = normalize_source_platform(source_platform)
    screenshot = await _read_validate_and_store(upload, settings)

    job = ProductImportJob(
        company_id=company_id,
        source_type="screenshot",
        source_platform=normalized_platform,
        status="processing",
    )
    asset = ProductImportAsset(
        import_job=job,
        file_name=screenshot.file_name,
        file_path=screenshot.file_path,
        mime_type=screenshot.mime_type,
        file_size=screenshot.file_size,
        width=screenshot.width,
        height=screenshot.height,
    )
    db.add(job)
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _remove_file_quietly(screenshot.resolved_path)
        raise
    db.refresh(job)
    db.refresh(asset)

    if not settings.bailian_vision_enabled:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_DISABLED",
            message="Vision analysis is disabled; a manual draft was created.",
        )
        return _build_screenshot_response(job, asset, draft)

    if not settings.bailian_vision_model:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_MODEL_NOT_CONFIGURED",
            message="Vision model is not configured; a manual draft was created.",
        )
        return _build_screenshot_response(job, asset, draft)

    try:
        completion = await _call_vision_model(
            client,
            screenshot=screenshot,
            source_platform=normalized_platform,
        )
        parsed = parse_json_object(completion.content)
        understanding = QwenProductUnderstandingResponse.model_validate(parsed)
    except BailianError as exc:
        draft = _create_fallback_draft(
            db,
            job,
            code=exc.code,
            message=_safe_fallback_message(exc.code, str(exc)),
        )
        return _build_screenshot_response(job, asset, draft)
    except AiJsonParseError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_PARSE_ERROR",
            message="Vision model response was not valid JSON; a manual draft was created.",
        )
        return _build_screenshot_response(job, asset, draft)
    except ValidationError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_SCHEMA_ERROR",
            message="Vision model response did not match the expected product draft schema.",
        )
        return _build_screenshot_response(job, asset, draft)

    job.model_used = completion.model
    if _requires_manual_blank_draft(understanding):
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_PRODUCT_NOT_IDENTIFIED",
            message="The screenshot did not identify a product clearly; a manual draft was created.",
            model_used=completion.model,
        )
        return _build_screenshot_response(job, asset, draft)

    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=understanding,
        source_platform_hint=normalized_platform,
    )
    return _build_screenshot_response(job, asset, draft)


def get_job_detail(db: Session, job_id: int) -> ProductImportJobDetailResponse | None:
    statement = (
        select(ProductImportJob)
        .options(
            selectinload(ProductImportJob.assets),
            selectinload(ProductImportJob.domestic_links),
            selectinload(ProductImportJob.drafts),
        )
        .where(ProductImportJob.id == job_id)
    )
    job = db.scalar(statement)
    if job is None:
        return None
    return ProductImportJobDetailResponse.model_validate(job)


def get_draft_detail(db: Session, draft_id: int) -> ProductDraftRead | None:
    draft = db.get(ProductDraft, draft_id)
    if draft is None:
        return None
    return ProductDraftRead.model_validate(draft)


def normalize_source_platform(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"taobao", "tmall", "pinduoduo", "jd", "unknown"} else "unknown"


async def _read_validate_and_store(upload: UploadFile, settings: Settings) -> StoredScreenshot:
    declared_mime = (upload.content_type or "").split(";")[0].strip().lower()
    if declared_mime not in ALLOWED_MIME_TYPES:
        raise ProductIntakeRequestError(415, "INVALID_IMAGE_TYPE", "Only PNG, JPEG, and WebP images are allowed.")

    data = await _read_upload_limited(upload, settings)
    detected_mime, extension, width, height = _validate_image_bytes(data)
    if detected_mime != declared_mime:
        raise ProductIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded file content did not match its image type.")

    base_dir = _resolve_upload_dir(settings.product_upload_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{extension}"
    target_path = (base_dir / file_name).resolve()
    try:
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise ProductIntakeRequestError(500, "UPLOAD_PATH_INVALID", "Upload path was not valid.") from exc

    try:
        target_path.write_bytes(data)
    except OSError as exc:
        raise ProductIntakeRequestError(500, "UPLOAD_WRITE_FAILED", "Uploaded image could not be saved.") from exc

    return StoredScreenshot(
        data=data,
        file_name=file_name,
        file_path=_storage_path_for_db(target_path),
        resolved_path=target_path,
        mime_type=detected_mime,
        file_size=len(data),
        width=width,
        height=height,
    )


async def _read_upload_limited(upload: UploadFile, settings: Settings) -> bytes:
    max_bytes = int(settings.max_product_image_size_mb * 1024 * 1024)
    chunks = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        if len(chunks) + len(chunk) > max_bytes:
            raise ProductIntakeRequestError(413, "IMAGE_TOO_LARGE", "Uploaded image exceeded the size limit.")
        chunks.extend(chunk)

    if not chunks:
        raise ProductIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded image was empty.")
    return bytes(chunks)


def _validate_image_bytes(data: bytes) -> tuple[str, str, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ProductIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded file was not a valid image.") from exc

    detected = FORMAT_TO_MIME_AND_EXT.get(image_format)
    if detected is None:
        raise ProductIntakeRequestError(415, "INVALID_IMAGE_TYPE", "Only PNG, JPEG, and WebP images are allowed.")
    mime_type, extension = detected
    return mime_type, extension, int(width), int(height)


def _resolve_upload_dir(value: str) -> Path:
    configured = Path(value).expanduser()
    if configured.is_absolute():
        return configured.resolve()
    return (PROJECT_ROOT / configured).resolve()


def _storage_path_for_db(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


async def _call_vision_model(
    client: BailianClient,
    *,
    screenshot: StoredScreenshot,
    source_platform: str,
) -> BailianChatCompletion:
    image_data_url = f"data:{screenshot.mime_type};base64,{base64.b64encode(screenshot.data).decode('ascii')}"
    messages = build_screenshot_product_understanding_messages(
        {
            "task": "extract_product_draft_from_user_uploaded_screenshot",
            "source_platform_hint": source_platform,
            "requirements": [
                "Return only the strict JSON object requested by the system prompt.",
                "Use null for fields that are not visible or not supported by screenshot evidence.",
                "Do not copy private buyer, account, order, address, phone, cookie, token, or secret content.",
            ],
        },
        image_data_url,
    )
    return await client.vision_chat(messages, temperature=0.2, max_tokens=1800, json_mode=True)


def _requires_manual_blank_draft(understanding: QwenProductUnderstandingResponse) -> bool:
    if not understanding.product_name_cn:
        return True
    return understanding.confidence_score < MIN_IDENTIFIED_CONFIDENCE


def _create_draft_from_understanding(
    db: Session,
    job: ProductImportJob,
    *,
    understanding: QwenProductUnderstandingResponse,
    source_platform_hint: str,
) -> ProductDraft:
    source_platform = understanding.source_platform
    if source_platform == "unknown" and source_platform_hint != "unknown":
        source_platform = source_platform_hint

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
        material=understanding.material,
        color_options=_sanitize_text_list(understanding.color_options),
        specification=understanding.specification,
        selling_points={
            "selling_points_cn": _sanitize_text_list(understanding.selling_points_cn),
            "selling_points_en": _sanitize_text_list(understanding.selling_points_en),
            "usage_scenarios": _sanitize_text_list(understanding.usage_scenarios),
            "cross_border_keywords_en": _sanitize_text_list(understanding.cross_border_keywords_en),
            "risk_notes": _sanitize_text_list(understanding.risk_notes),
        },
        target_users=_sanitize_text_list(understanding.target_users),
        source_platform=source_platform,
        evidence=_sanitize_evidence(understanding),
        confidence_score=confidence,
        status="draft",
    )
    job.source_platform = source_platform
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        job.status = "draft_ready_with_low_confidence"
        job.error_code = "LOW_CONFIDENCE"
        job.error_message = "Draft requires manual review because model confidence is low."
    else:
        job.status = "draft_ready"
        job.error_code = None
        job.error_message = None
    db.add(draft)
    db.commit()
    db.refresh(job)
    db.refresh(draft)
    return draft


def _create_fallback_draft(
    db: Session,
    job: ProductImportJob,
    *,
    code: str,
    message: str,
    model_used: str | None = None,
) -> ProductDraft:
    safe_message = sanitize_intake_text(message, max_length=240)
    if model_used:
        job.model_used = model_used
    job.status = "draft_ready_with_low_confidence"
    job.error_code = code
    job.error_message = safe_message
    draft = ProductDraft(
        import_job_id=job.id,
        company_id=job.company_id,
        source_platform=job.source_platform,
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
    db.refresh(draft)
    return draft


def _build_screenshot_response(
    job: ProductImportJob,
    asset: ProductImportAsset,
    draft: ProductDraft,
) -> ProductScreenshotIntakeResponse:
    draft_summary = ProductDraftRead.model_validate(draft)
    next_action = "review_draft"
    if job.error_code and job.error_code != "LOW_CONFIDENCE":
        next_action = "manual_fill"
    elif draft_summary.low_confidence:
        next_action = "manual_review"
    return ProductScreenshotIntakeResponse(
        import_job_id=job.id,
        draft_id=draft.id,
        job_status=job.status,
        draft_status=draft.status,
        low_confidence=draft_summary.low_confidence,
        error_code=job.error_code,
        error_message=job.error_message,
        next_action=next_action,
        asset=ProductImportAssetRead.model_validate(asset),
        draft=ProductDraftSummary.model_validate(draft),
    )


def _safe_fallback_message(code: str, raw_message: str) -> str:
    safe = sanitize_intake_text(raw_message, max_length=160) or "Vision analysis failed."
    generic_by_code = {
        "BAILIAN_NOT_CONFIGURED": "Bailian API key is not configured; a manual draft was created.",
        "BAILIAN_AUTHENTICATION_ERROR": "Vision provider authentication failed; a manual draft was created.",
        "BAILIAN_RATE_LIMITED": "Vision provider rate limit was reached; a manual draft was created.",
        "BAILIAN_TIMEOUT": "Vision analysis timed out; a manual draft was created.",
        "BAILIAN_UPSTREAM_ERROR": "Vision provider returned an upstream error; a manual draft was created.",
        "BAILIAN_RESPONSE_ERROR": "Vision provider response could not be read; a manual draft was created.",
    }
    return generic_by_code.get(code, safe)


def _parse_weight_kg(value: str | None) -> Decimal | None:
    if not value:
        return None
    text = value.strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|千克|公斤|g|克)\b", text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    unit = match.group(2)
    if unit in {"g", "克"}:
        amount = amount / Decimal("1000")
    return amount


def _sanitize_evidence(understanding: QwenProductUnderstandingResponse) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for item in understanding.evidence:
        sanitized.append(
            {
                "field": sanitize_intake_text(item.field, max_length=128) or "unknown",
                "source": item.source,
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


def _limit_text(value: str | None, max_length: int) -> str | None:
    text = sanitize_intake_text(value, max_length=max_length)
    return text or None


def sanitize_intake_text(value: object, *, max_length: int = 240) -> str | None:
    if value is None:
        return None
    text = redact_text(str(value)) or ""
    text = _WINDOWS_PATH_RE.sub("[REDACTED_PATH]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _LONG_NUMBER_RE.sub("[REDACTED_NUMBER]", text)
    text = " ".join(text.split()).strip()
    if not text:
        return None
    return text[:max_length]


def _remove_file_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
