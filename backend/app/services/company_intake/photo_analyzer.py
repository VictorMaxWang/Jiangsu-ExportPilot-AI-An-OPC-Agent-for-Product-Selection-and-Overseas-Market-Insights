from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.models import CompanyDraft, CompanyImportAsset, CompanyImportJob
from app.schemas.company_intake import (
    AiResultType,
    CompanyDraftRead,
    CompanyDraftSummary,
    CompanyImportAssetRead,
    CompanyImportJobDetailResponse,
    CompanyPhotoIntakeResponse,
    QwenCompanyUnderstandingResponse,
)
from app.services.ai import (
    BailianChatCompletion,
    BailianClient,
    BailianError,
)
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_company_photo_understanding_messages
from app.utils.redaction import redact_text


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
FORMAT_TO_MIME_AND_EXT = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}
MAX_COMPANY_PHOTO_UPLOADS = 4
PRIMARY_IMAGE_ROLES = {
    "business_license",
    "license",
    "main",
    "primary",
    "cover",
    "business_card",
    "name_card",
}
LOW_CONFIDENCE_THRESHOLD = Decimal("0.65")
MIN_IDENTIFIED_CONFIDENCE = Decimal("0.35")
VISION_PRODUCTION_FAILURE_MESSAGE = (
    "Vision analysis is unavailable or returned unusable company intake output; "
    "please manually review the company draft."
)
Image.MAX_IMAGE_PIXELS = 50_000_000

_PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_ID_CARD_RE = re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])")
_CREDIT_CODE_RE = re.compile(r"(?<![0-9A-Za-z])[0-9A-Z]{18}(?![0-9A-Za-z])", re.IGNORECASE)
_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")
_WINDOWS_PATH_RE = re.compile(r"(?i)[a-z]:\\[^\s]+")


class CompanyIntakeRequestError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class StoredCompanyPhoto:
    data: bytes
    file_name: str
    file_path: str
    resolved_path: Path
    mime_type: str
    file_size: int
    width: int
    height: int
    image_index: int
    image_role: str
    storage_error_code: str | None = None
    storage_error_message: str | None = None


async def analyze_company_photo_uploads(
    db: Session,
    *,
    uploads: list[UploadFile],
    source_platform: str | None,
    image_roles: list[str] | None,
    client: BailianClient,
    settings: Settings | None = None,
) -> CompanyPhotoIntakeResponse:
    settings = settings or get_settings()
    upload_count = len(uploads)
    if upload_count < 1:
        raise CompanyIntakeRequestError(422, "NO_IMAGES_UPLOADED", "At least one company image is required.")
    if upload_count > MAX_COMPANY_PHOTO_UPLOADS:
        raise CompanyIntakeRequestError(422, "TOO_MANY_IMAGES", "A maximum of 4 company images can be uploaded.")

    normalized_platform = normalize_source_platform(source_platform)
    normalized_roles = _normalize_image_roles(image_roles or [], upload_count)
    photos = [
        await _read_validate_upload(
            upload,
            settings,
            image_index=index,
            image_role=normalized_roles[index],
        )
        for index, upload in enumerate(uploads)
    ]

    stored_photos = [_store_photo(photo) for photo in photos]
    primary_index = _primary_image_index(stored_photos)
    job = CompanyImportJob(
        source_type="photo",
        source_platform=normalized_platform,
        status="processing",
    )
    assets = [
        CompanyImportAsset(
            import_job=job,
            file_name=photo.file_name,
            file_path=photo.file_path,
            mime_type=photo.mime_type,
            file_size=photo.file_size,
            width=photo.width,
            height=photo.height,
            image_index=photo.image_index,
            image_role=photo.image_role,
            is_primary=photo.image_index == primary_index,
        )
        for photo in stored_photos
    ]
    db.add(job)
    for asset in assets:
        db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        for photo in stored_photos:
            if photo.storage_error_code is None:
                _remove_file_quietly(photo.resolved_path)
        raise
    db.refresh(job)
    for asset in assets:
        db.refresh(asset)

    analysis_photos = [photo for photo in stored_photos if photo.storage_error_code is None]
    failed_images = [
        _image_failure(
            photo.image_index,
            photo.image_role,
            photo.storage_error_code or "IMAGE_FAILED",
            photo.storage_error_message or "Image storage failed.",
        )
        for photo in stored_photos
        if photo.storage_error_code is not None
    ]

    if not analysis_photos:
        draft = _create_fallback_draft(
            db,
            job,
            code="UPLOAD_STORAGE_UNAVAILABLE",
            message="Company image storage is temporarily unavailable; a manual draft was created.",
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_enabled:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_DISABLED",
            message="Vision analysis is disabled; please manually complete the company draft.",
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_model:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_MODEL_NOT_CONFIGURED",
            message="Vision model is not configured; please manually complete the company draft.",
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    manual_code = "PARTIAL_IMAGE_UPLOAD_FAILED" if failed_images else None
    manual_message = "Some uploaded images could not be stored and require manual review." if failed_images else None
    try:
        completion = await _call_company_vision_model(
            client,
            photos=analysis_photos,
            source_platform=normalized_platform,
        )
        job.model_used = completion.model
        understanding = _parse_understanding_completion(completion)
    except BailianError as exc:
        draft = _create_fallback_draft(
            db,
            job,
            code=exc.code,
            message=_safe_fallback_message(exc.code, str(exc)),
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)
    except AiJsonParseError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_PARSE_ERROR",
            message=VISION_PRODUCTION_FAILURE_MESSAGE,
            model_used=job.model_used,
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)
    except ValidationError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_SCHEMA_ERROR",
            message=VISION_PRODUCTION_FAILURE_MESSAGE,
            model_used=job.model_used,
        )
        return _build_photo_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    if _requires_manual_blank_draft(understanding):
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_COMPANY_NOT_IDENTIFIED",
            message="The uploaded images did not identify a company clearly; a manual draft was created.",
            model_used=completion.model,
        )
        return _build_photo_response(job, assets, draft, ai_result_type="manual_required", ai_fallback_used=False)

    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=understanding,
        evidence_image_roles=_image_role_map(job),
        manual_required_code=manual_code,
        manual_required_message=manual_message,
    )
    result_type: AiResultType = "manual_required" if draft.confidence_score < LOW_CONFIDENCE_THRESHOLD else "real_qwen"
    return _build_photo_response(job, assets, draft, ai_result_type=result_type, ai_fallback_used=False)


def get_job_detail(db: Session, job_id: int) -> CompanyImportJobDetailResponse | None:
    statement = (
        select(CompanyImportJob)
        .options(
            selectinload(CompanyImportJob.assets),
            selectinload(CompanyImportJob.drafts),
        )
        .where(CompanyImportJob.id == job_id)
    )
    job = db.scalar(statement)
    if job is None:
        return None
    return CompanyImportJobDetailResponse.model_validate(job)


def get_draft_detail(db: Session, draft_id: int) -> CompanyDraftRead | None:
    draft = db.get(CompanyDraft, draft_id)
    if draft is None:
        return None
    return CompanyDraftRead.model_validate(draft)


def normalize_source_platform(value: str | None) -> str:
    text = sanitize_company_intake_text(value, max_length=32)
    if not text:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return normalized[:32] or "unknown"


def sanitize_company_intake_text(value: object, *, max_length: int = 240) -> str | None:
    if value is None:
        return None
    text = redact_text(str(value)) or ""
    text = _WINDOWS_PATH_RE.sub("[REDACTED_PATH]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _CREDIT_CODE_RE.sub("[REDACTED_CREDIT_CODE]", text)
    text = _ID_CARD_RE.sub("[REDACTED_ID_CARD]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _LONG_NUMBER_RE.sub("[REDACTED_NUMBER]", text)
    text = " ".join(text.split()).strip()
    if not text:
        return None
    return text[:max_length]


def sanitize_credit_code_suffix(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().upper()
    credit_match = _CREDIT_CODE_RE.search(raw)
    if credit_match:
        return credit_match.group(0)[-4:]
    compact = re.sub(r"[^0-9A-Z]", "", raw)
    if len(compact) >= 4:
        return compact[-4:]
    return compact or None


def sanitize_text_list(values: object, *, max_length: int = 180) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_company_intake_text(value, max_length=max_length)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


def normalize_target_countries(values: object) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_company_intake_text(value, max_length=16)
        if not text:
            continue
        code = re.sub(r"[^A-Za-z]", "", text).upper()
        if len(code) != 2 or code in seen:
            continue
        cleaned.append(code)
        seen.add(code)
    return cleaned[:20]


def _normalize_image_roles(values: list[str], expected_count: int) -> list[str]:
    if not values:
        return ["unknown"] * expected_count
    if len(values) != expected_count:
        raise CompanyIntakeRequestError(
            422,
            "IMAGE_ROLES_MISMATCH",
            "image_roles must be omitted or match the number of uploaded files.",
        )
    return [_normalize_image_role(value) for value in values]


def _normalize_image_role(value: str | None) -> str:
    text = sanitize_company_intake_text(value, max_length=64)
    if not text:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return normalized[:64] or "unknown"


def _primary_image_index(photos: list[StoredCompanyPhoto]) -> int:
    for photo in photos:
        if photo.image_role in PRIMARY_IMAGE_ROLES:
            return photo.image_index
    return photos[0].image_index


def _image_failure(upload_index: int, image_role: str, code: str, message: str) -> dict[str, object]:
    return {
        "image_index": upload_index,
        "image_role": sanitize_company_intake_text(image_role, max_length=64) or "unknown",
        "code": sanitize_company_intake_text(code, max_length=64) or "IMAGE_FAILED",
        "message": sanitize_company_intake_text(message, max_length=180) or "Image could not be processed.",
    }


async def _read_validate_upload(
    upload: UploadFile,
    settings: Settings,
    *,
    image_index: int,
    image_role: str,
) -> StoredCompanyPhoto:
    declared_mime = (upload.content_type or "").split(";")[0].strip().lower()
    if declared_mime not in ALLOWED_MIME_TYPES:
        raise CompanyIntakeRequestError(415, "INVALID_IMAGE_TYPE", "Only PNG, JPEG, and WebP images are allowed.")

    data = await _read_upload_limited(upload, settings)
    detected_mime, extension, width, height = _validate_image_bytes(data)
    if detected_mime != declared_mime:
        raise CompanyIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded file content did not match its image type.")

    base_dir = _resolve_upload_dir(settings.company_upload_dir)
    file_name = f"{uuid.uuid4().hex}{extension}"
    target_path = (base_dir / file_name).resolve()
    try:
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise CompanyIntakeRequestError(500, "UPLOAD_PATH_INVALID", "Upload path was not valid.") from exc

    return StoredCompanyPhoto(
        data=data,
        file_name=file_name,
        file_path=_storage_path_for_db(target_path),
        resolved_path=target_path,
        mime_type=detected_mime,
        file_size=len(data),
        width=width,
        height=height,
        image_index=image_index,
        image_role=image_role,
    )


def _store_photo(photo: StoredCompanyPhoto) -> StoredCompanyPhoto:
    try:
        photo.resolved_path.parent.mkdir(parents=True, exist_ok=True)
        photo.resolved_path.write_bytes(photo.data)
    except OSError:
        return replace(
            photo,
            storage_error_code="UPLOAD_STORAGE_UNAVAILABLE",
            storage_error_message="Company image storage is temporarily unavailable; a manual draft was created.",
        )
    return photo


async def _read_upload_limited(upload: UploadFile, settings: Settings) -> bytes:
    max_bytes = int(settings.max_company_image_size_mb * 1024 * 1024)
    chunks = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        if len(chunks) + len(chunk) > max_bytes:
            raise CompanyIntakeRequestError(413, "IMAGE_TOO_LARGE", "Uploaded image exceeded the size limit.")
        chunks.extend(chunk)

    if not chunks:
        raise CompanyIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded image was empty.")
    return bytes(chunks)


def _validate_image_bytes(data: bytes) -> tuple[str, str, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise CompanyIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded file was not a valid image.") from exc

    detected = FORMAT_TO_MIME_AND_EXT.get(image_format)
    if detected is None:
        raise CompanyIntakeRequestError(415, "INVALID_IMAGE_TYPE", "Only PNG, JPEG, and WebP images are allowed.")
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


async def _call_company_vision_model(
    client: BailianClient,
    *,
    photos: list[StoredCompanyPhoto],
    source_platform: str,
) -> BailianChatCompletion:
    image_catalog = [
        {
            "image_index": photo.image_index,
            "image_role": photo.image_role,
            "mime_type": photo.mime_type,
            "width": photo.width,
            "height": photo.height,
        }
        for photo in photos
    ]
    image_parts = [
        {
            "image_index": str(photo.image_index),
            "image_role": photo.image_role,
            "image_data_url": f"data:{photo.mime_type};base64,{base64.b64encode(photo.data).decode('ascii')}",
        }
        for photo in photos
    ]
    messages = build_company_photo_understanding_messages(
        {
            "task": "extract_company_draft_from_user_uploaded_company_photos",
            "source_platform_hint": source_platform,
            "images": image_catalog,
            "requirements": [
                "Return only the strict JSON object requested by the system prompt.",
                "Use null or [] for fields that are not visible or not supported by image evidence.",
                "Use the supplied image_index and image_role for every image-derived evidence item.",
                "Do not copy private phone, ID card, full credit code, address, bank, QR secret, cookie, token, or header content.",
            ],
        },
        image_parts,
    )
    return await client.vision_chat(messages, temperature=0.2, max_tokens=2200, json_mode=True)


def _parse_understanding_completion(completion: BailianChatCompletion) -> QwenCompanyUnderstandingResponse:
    parsed = parse_json_object(completion.content)
    return QwenCompanyUnderstandingResponse.model_validate(parsed)


def _requires_manual_blank_draft(understanding: QwenCompanyUnderstandingResponse) -> bool:
    if _has_any_company_signal(understanding):
        return False
    return understanding.confidence_score < MIN_IDENTIFIED_CONFIDENCE


def _has_any_company_signal(understanding: QwenCompanyUnderstandingResponse) -> bool:
    return any(
        [
            understanding.company_name,
            understanding.region,
            understanding.industry,
            understanding.description,
            understanding.main_products,
            understanding.website,
            understanding.contact_role,
        ]
    )


def _create_draft_from_understanding(
    db: Session,
    job: CompanyImportJob,
    *,
    understanding: QwenCompanyUnderstandingResponse,
    evidence_image_roles: dict[int, str],
    manual_required_code: str | None = None,
    manual_required_message: str | None = None,
) -> CompanyDraft:
    confidence = understanding.confidence_score
    company_name = sanitize_company_intake_text(understanding.company_name, max_length=255)
    if (manual_required_code or not company_name) and confidence >= LOW_CONFIDENCE_THRESHOLD:
        confidence = Decimal("0.6400")

    draft = CompanyDraft(
        import_job_id=job.id,
        company_name=company_name,
        credit_code_suffix=sanitize_credit_code_suffix(understanding.credit_code_suffix),
        region=sanitize_company_intake_text(understanding.region, max_length=128),
        industry=sanitize_company_intake_text(understanding.industry, max_length=128),
        main_products=sanitize_text_list(understanding.main_products),
        target_countries=normalize_target_countries(understanding.target_countries),
        website=sanitize_company_intake_text(understanding.website, max_length=2048),
        description=sanitize_company_intake_text(understanding.description, max_length=4000),
        contact_role=sanitize_company_intake_text(understanding.contact_role, max_length=128),
        evidence=_sanitize_evidence(understanding, image_roles=evidence_image_roles),
        risk_notes=sanitize_text_list(understanding.risk_notes),
        confidence_score=confidence,
        status="draft",
    )
    if manual_required_code:
        job.status = "draft_ready_with_low_confidence"
        job.error_code = manual_required_code
        job.error_message = sanitize_company_intake_text(manual_required_message, max_length=240)
    elif confidence < LOW_CONFIDENCE_THRESHOLD:
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
    job: CompanyImportJob,
    *,
    code: str,
    message: str,
    model_used: str | None = None,
) -> CompanyDraft:
    safe_message = sanitize_company_intake_text(message, max_length=240)
    if model_used:
        job.model_used = model_used
    job.status = "draft_ready_with_low_confidence"
    job.error_code = sanitize_company_intake_text(code, max_length=64)
    job.error_message = safe_message
    draft = CompanyDraft(
        import_job_id=job.id,
        confidence_score=Decimal("0.0000"),
        target_countries=[],
        status="draft",
        main_products=[],
        evidence=[],
        risk_notes=[safe_message] if safe_message else [],
    )
    db.add(draft)
    db.commit()
    db.refresh(job)
    db.refresh(draft)
    return draft


def _sanitize_evidence(
    understanding: QwenCompanyUnderstandingResponse,
    *,
    image_roles: dict[int, str],
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    default_index = min(image_roles) if image_roles else 0
    default_role = image_roles.get(default_index, "unknown") if image_roles else "unknown"
    for item in understanding.evidence:
        image_index = item.image_index if item.image_index is not None else default_index
        if image_roles and image_index not in image_roles:
            image_index = default_index
        image_role = image_roles.get(image_index, default_role) if image_roles else (item.image_role or default_role)
        sanitized.append(
            {
                "field": sanitize_company_intake_text(item.field, max_length=128) or "unknown",
                "source": item.source,
                "image_index": image_index,
                "image_role": sanitize_company_intake_text(image_role, max_length=64) or "unknown",
                "value": sanitize_company_intake_text(item.value, max_length=180),
            }
        )
    return sanitized


def _image_role_map(job: CompanyImportJob) -> dict[int, str]:
    return {
        int(asset.image_index): sanitize_company_intake_text(asset.image_role, max_length=64) or "unknown"
        for asset in sorted(job.assets, key=lambda asset: asset.image_index)
    }


def _build_photo_response(
    job: CompanyImportJob,
    assets: list[CompanyImportAsset],
    draft: CompanyDraft,
    *,
    ai_result_type: AiResultType,
    ai_fallback_used: bool,
) -> CompanyPhotoIntakeResponse:
    ordered_assets = sorted(assets, key=lambda asset: asset.image_index)
    primary_asset = next((asset for asset in ordered_assets if asset.is_primary), ordered_assets[0])
    draft_summary = CompanyDraftRead.model_validate(draft)
    next_action = "review_draft"
    if job.error_code and job.error_code != "LOW_CONFIDENCE":
        next_action = "manual_fill"
    elif draft_summary.low_confidence:
        next_action = "manual_review"
    return CompanyPhotoIntakeResponse(
        import_job_id=job.id,
        draft_id=draft.id,
        job_status=job.status,
        draft_status=draft.status,
        low_confidence=draft_summary.low_confidence,
        ai_result_type=ai_result_type,
        ai_fallback_used=ai_fallback_used,
        model_used=job.model_used,
        error_code=job.error_code,
        error_message=job.error_message,
        next_action=next_action,
        asset=CompanyImportAssetRead.model_validate(primary_asset),
        assets=[CompanyImportAssetRead.model_validate(asset) for asset in ordered_assets],
        draft=CompanyDraftSummary.model_validate(draft),
    )


def _safe_fallback_message(code: str, raw_message: str) -> str:
    safe = sanitize_company_intake_text(raw_message, max_length=160) or "Vision analysis failed."
    generic_by_code = {
        "BAILIAN_VISION_DISABLED": "Vision analysis is disabled; please manually complete the company draft.",
        "BAILIAN_VISION_MODEL_NOT_CONFIGURED": "Vision model is not configured; please manually complete the company draft.",
        "BAILIAN_NOT_CONFIGURED": "Bailian API key is not configured; a manual company draft was created.",
        "BAILIAN_AUTHENTICATION_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_RATE_LIMITED": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_TIMEOUT": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_UPSTREAM_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_RESPONSE_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
    }
    return generic_by_code.get(code, safe)


def _remove_file_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
