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
    AiResultType,
    ProductDraftSummary,
    ProductDraftRead,
    ProductImportAssetRead,
    ProductImportJobDetailResponse,
    ProductScreenshotIntakeResponse,
    ProductScreenshotsIntakeResponse,
    QwenProductUnderstandingResponse,
)
from app.services.ai import (
    BailianAuthenticationError,
    BailianChatCompletion,
    BailianClient,
    BailianError,
    BailianRateLimitError,
)
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import (
    build_multi_screenshot_product_understanding_messages,
    build_screenshot_product_understanding_messages,
)
from app.utils.redaction import redact_text


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
FORMAT_TO_MIME_AND_EXT = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}
MAX_SCREENSHOT_UPLOADS = 8
PRIMARY_IMAGE_ROLES = {"main", "primary", "cover", "hero"}
LOW_CONFIDENCE_THRESHOLD = Decimal("0.65")
MIN_IDENTIFIED_CONFIDENCE = Decimal("0.35")
VISION_PRODUCTION_FAILURE_MESSAGE = "视觉模型未通过生产验收，请先上传截图后人工补全或配置可用视觉模型。"
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
    image_index: int = 0
    image_role: str = "screenshot"
    storage_error_code: str | None = None
    storage_error_message: str | None = None


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
        image_index=0,
        image_role="screenshot",
        is_primary=True,
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

    if screenshot.storage_error_code:
        draft = _create_fallback_draft(
            db,
            job,
            code=screenshot.storage_error_code,
            message=screenshot.storage_error_message
            or "Screenshot storage is temporarily unavailable; please manually review the draft.",
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_enabled:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_DISABLED",
            message="视觉模型未启用，请人工补全商品信息。",
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_model:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_MODEL_NOT_CONFIGURED",
            message="视觉模型未配置，请配置视觉模型后再启用截图识别。",
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)

    try:
        completion = await _call_vision_model(
            client,
            screenshot=screenshot,
            source_platform=normalized_platform,
        )
    except BailianError as exc:
        draft = _create_fallback_draft(
            db,
            job,
            code=exc.code,
            message=_safe_fallback_message(exc.code, str(exc)),
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)

    job.model_used = completion.model
    try:
        parsed = parse_json_object(completion.content)
        understanding = QwenProductUnderstandingResponse.model_validate(parsed)
    except AiJsonParseError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_PARSE_ERROR",
            message=VISION_PRODUCTION_FAILURE_MESSAGE,
            model_used=completion.model,
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)
    except ValidationError:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_RESPONSE_SCHEMA_ERROR",
            message=VISION_PRODUCTION_FAILURE_MESSAGE,
            model_used=completion.model,
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="fallback", ai_fallback_used=True)

    if _requires_manual_blank_draft(understanding):
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_PRODUCT_NOT_IDENTIFIED",
            message="The screenshot did not identify a product clearly; a manual draft was created.",
            model_used=completion.model,
        )
        return _build_screenshot_response(job, asset, draft, ai_result_type="manual_required", ai_fallback_used=False)

    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=understanding,
        source_platform_hint=normalized_platform,
    )
    result_type: AiResultType = "manual_required" if understanding.confidence_score < LOW_CONFIDENCE_THRESHOLD else "real_qwen"
    return _build_screenshot_response(job, asset, draft, ai_result_type=result_type, ai_fallback_used=False)


async def analyze_screenshot_uploads(
    db: Session,
    *,
    company_id: int,
    uploads: list[UploadFile],
    source_platform: str | None,
    image_roles: list[str] | None,
    client: BailianClient,
    settings: Settings | None = None,
) -> ProductScreenshotsIntakeResponse:
    settings = settings or get_settings()
    if db.get(Company, company_id) is None:
        raise ProductIntakeRequestError(404, "COMPANY_NOT_FOUND", "Company not found")

    upload_count = len(uploads)
    if upload_count < 1:
        raise ProductIntakeRequestError(422, "NO_IMAGES_UPLOADED", "At least one product image is required.")
    if upload_count > MAX_SCREENSHOT_UPLOADS:
        raise ProductIntakeRequestError(422, "TOO_MANY_IMAGES", "A maximum of 8 product images can be uploaded.")

    normalized_platform = normalize_source_platform(source_platform)
    normalized_roles = _normalize_image_roles(image_roles or [], upload_count)
    screenshots: list[StoredScreenshot] = []
    failed_images: list[dict[str, object]] = []

    for upload_index, upload in enumerate(uploads):
        image_role = normalized_roles[upload_index]
        try:
            screenshot = await _read_validate_and_store(
                upload,
                settings,
                image_index=len(screenshots),
                image_role=image_role,
            )
        except ProductIntakeRequestError as exc:
            failed_images.append(_image_failure(upload_index, image_role, exc.code, exc.message))
            continue

        screenshots.append(screenshot)
        if screenshot.storage_error_code:
            failed_images.append(
                _image_failure(
                    upload_index,
                    image_role,
                    screenshot.storage_error_code,
                    screenshot.storage_error_message or "Image storage failed.",
                )
            )

    if not screenshots:
        first_failure = failed_images[0] if failed_images else {}
        raise ProductIntakeRequestError(
            422,
            str(first_failure.get("code") or "INVALID_IMAGE_CONTENT"),
            str(first_failure.get("message") or "No valid product images were uploaded."),
        )

    primary_index = _primary_image_index(screenshots)
    job = ProductImportJob(
        company_id=company_id,
        source_type="multi_image",
        source_platform=normalized_platform,
        status="processing",
    )
    assets = [
        ProductImportAsset(
            import_job=job,
            file_name=screenshot.file_name,
            file_path=screenshot.file_path,
            mime_type=screenshot.mime_type,
            file_size=screenshot.file_size,
            width=screenshot.width,
            height=screenshot.height,
            image_index=screenshot.image_index,
            image_role=screenshot.image_role,
            is_primary=screenshot.image_index == primary_index,
        )
        for screenshot in screenshots
    ]
    db.add(job)
    for asset in assets:
        db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        for screenshot in screenshots:
            _remove_file_quietly(screenshot.resolved_path)
        raise
    db.refresh(job)
    for asset in assets:
        db.refresh(asset)

    summary = _multi_image_summary_for_job(
        job,
        analysis_strategy="pending",
        failed_images=failed_images,
    )
    analysis_screenshots = [screenshot for screenshot in screenshots if not screenshot.storage_error_code]
    if not analysis_screenshots:
        draft = _create_fallback_draft(
            db,
            job,
            code="UPLOAD_STORAGE_UNAVAILABLE",
            message="Product image storage is temporarily unavailable; a manual draft was created.",
            multi_image_summary=summary,
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_enabled:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_DISABLED",
            message="Vision analysis is disabled; please manually complete the product draft.",
            multi_image_summary=summary,
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    if not settings.bailian_vision_model:
        draft = _create_fallback_draft(
            db,
            job,
            code="BAILIAN_VISION_MODEL_NOT_CONFIGURED",
            message="Vision model is not configured; please manually complete the product draft.",
            multi_image_summary=summary,
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    role_map = _image_role_map(job)
    manual_code = "PARTIAL_IMAGE_UPLOAD_FAILED" if failed_images else None
    manual_message = "Some uploaded images could not be used and require manual review." if failed_images else None

    try:
        completion = await _call_multi_image_vision_model(
            client,
            screenshots=analysis_screenshots,
            source_platform=normalized_platform,
        )
        job.model_used = completion.model
        understanding = _parse_understanding_completion(completion)
    except (BailianAuthenticationError, BailianRateLimitError) as exc:
        draft = _create_fallback_draft(
            db,
            job,
            code=exc.code,
            message=_safe_fallback_message(exc.code, str(exc)),
            multi_image_summary=_multi_image_summary_for_job(
                job,
                analysis_strategy="multi_image_failed",
                failed_images=failed_images,
            ),
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)
    except (BailianError, AiJsonParseError, ValidationError):
        return await _analyze_images_individually(
            db,
            job=job,
            assets=assets,
            screenshots=analysis_screenshots,
            source_platform=normalized_platform,
            failed_images=failed_images,
            client=client,
        )

    if _requires_manual_blank_draft(understanding):
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_PRODUCT_NOT_IDENTIFIED",
            message="The uploaded images did not identify a product clearly; a manual draft was created.",
            model_used=completion.model,
            multi_image_summary=_multi_image_summary_for_job(
                job,
                analysis_strategy="multi_image",
                failed_images=failed_images,
            ),
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="manual_required", ai_fallback_used=False)

    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=understanding,
        source_platform_hint=normalized_platform,
        evidence_image_roles=role_map,
        manual_required_code=manual_code,
        manual_required_message=manual_message,
        multi_image_summary=_multi_image_summary_for_job(
            job,
            analysis_strategy="multi_image",
            failed_images=failed_images,
        ),
    )
    result_type: AiResultType = "manual_required" if draft.confidence_score < LOW_CONFIDENCE_THRESHOLD else "real_qwen"
    return _build_screenshots_response(job, assets, draft, ai_result_type=result_type, ai_fallback_used=False)


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


def _normalize_image_roles(values: list[str], expected_count: int) -> list[str]:
    if not values:
        return ["unknown"] * expected_count
    if len(values) != expected_count:
        raise ProductIntakeRequestError(
            422,
            "IMAGE_ROLES_MISMATCH",
            "image_roles must be omitted or match the number of uploaded files.",
        )
    return [_normalize_image_role(value) for value in values]


def _normalize_image_role(value: str | None) -> str:
    text = sanitize_intake_text(value, max_length=64)
    if not text:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return normalized[:64] or "unknown"


def _primary_image_index(screenshots: list[StoredScreenshot]) -> int:
    for screenshot in screenshots:
        if screenshot.image_role in PRIMARY_IMAGE_ROLES:
            return screenshot.image_index
    return screenshots[0].image_index


def _image_failure(upload_index: int, image_role: str, code: str, message: str) -> dict[str, object]:
    return {
        "image_index": upload_index,
        "image_role": sanitize_intake_text(image_role, max_length=64) or "unknown",
        "code": sanitize_intake_text(code, max_length=64) or "IMAGE_FAILED",
        "message": sanitize_intake_text(message, max_length=180) or "Image could not be processed.",
    }


async def _read_validate_and_store(
    upload: UploadFile,
    settings: Settings,
    *,
    image_index: int = 0,
    image_role: str = "screenshot",
) -> StoredScreenshot:
    declared_mime = (upload.content_type or "").split(";")[0].strip().lower()
    if declared_mime not in ALLOWED_MIME_TYPES:
        raise ProductIntakeRequestError(415, "INVALID_IMAGE_TYPE", "Only PNG, JPEG, and WebP images are allowed.")

    data = await _read_upload_limited(upload, settings)
    detected_mime, extension, width, height = _validate_image_bytes(data)
    if detected_mime != declared_mime:
        raise ProductIntakeRequestError(422, "INVALID_IMAGE_CONTENT", "Uploaded file content did not match its image type.")

    base_dir = _resolve_upload_dir(settings.product_upload_dir)
    file_name = f"{uuid.uuid4().hex}{extension}"
    target_path = (base_dir / file_name).resolve()
    try:
        target_path.relative_to(base_dir)
    except ValueError as exc:
        raise ProductIntakeRequestError(500, "UPLOAD_PATH_INVALID", "Upload path was not valid.") from exc

    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
    except OSError as exc:
        return StoredScreenshot(
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
            storage_error_code="UPLOAD_STORAGE_UNAVAILABLE",
            storage_error_message="Screenshot storage is temporarily unavailable; a manual draft was created.",
        )

    return StoredScreenshot(
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


async def _call_multi_image_vision_model(
    client: BailianClient,
    *,
    screenshots: list[StoredScreenshot],
    source_platform: str,
) -> BailianChatCompletion:
    image_catalog = [
        {
            "image_index": screenshot.image_index,
            "image_role": screenshot.image_role,
            "mime_type": screenshot.mime_type,
            "width": screenshot.width,
            "height": screenshot.height,
        }
        for screenshot in screenshots
    ]
    image_parts = [
        {
            "image_index": str(screenshot.image_index),
            "image_role": screenshot.image_role,
            "image_data_url": f"data:{screenshot.mime_type};base64,{base64.b64encode(screenshot.data).decode('ascii')}",
        }
        for screenshot in screenshots
    ]
    messages = build_multi_screenshot_product_understanding_messages(
        {
            "task": "extract_product_draft_from_user_uploaded_product_screenshots",
            "source_platform_hint": source_platform,
            "images": image_catalog,
            "requirements": [
                "Return only the strict JSON object requested by the system prompt.",
                "Use the supplied image_index and image_role for each image-derived evidence item.",
                "Use null for fields that are not visible or not supported by screenshot evidence.",
                "Do not copy private buyer, account, order, address, phone, cookie, token, or secret content.",
            ],
        },
        image_parts,
    )
    return await client.vision_chat(messages, temperature=0.2, max_tokens=2400, json_mode=True)


def _parse_understanding_completion(completion: BailianChatCompletion) -> QwenProductUnderstandingResponse:
    parsed = parse_json_object(completion.content)
    return QwenProductUnderstandingResponse.model_validate(parsed)


async def _analyze_images_individually(
    db: Session,
    *,
    job: ProductImportJob,
    assets: list[ProductImportAsset],
    screenshots: list[StoredScreenshot],
    source_platform: str,
    failed_images: list[dict[str, object]],
    client: BailianClient,
) -> ProductScreenshotsIntakeResponse:
    successes: list[tuple[QwenProductUnderstandingResponse, StoredScreenshot, str]] = []
    fallback_failures = list(failed_images)
    for screenshot in screenshots:
        try:
            completion = await _call_vision_model(client, screenshot=screenshot, source_platform=source_platform)
            understanding = _parse_understanding_completion(completion)
        except (BailianAuthenticationError, BailianRateLimitError) as exc:
            draft = _create_fallback_draft(
                db,
                job,
                code=exc.code,
                message=_safe_fallback_message(exc.code, str(exc)),
                multi_image_summary=_multi_image_summary_for_job(
                    job,
                    analysis_strategy="per_image_failed",
                    failed_images=fallback_failures,
                ),
            )
            return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)
        except (BailianError, AiJsonParseError, ValidationError) as exc:
            fallback_failures.append(
                _image_failure(
                    screenshot.image_index,
                    screenshot.image_role,
                    _failure_code(exc),
                    "Image analysis failed and requires manual review.",
                )
            )
            continue

        if _requires_manual_blank_draft(understanding):
            fallback_failures.append(
                _image_failure(
                    screenshot.image_index,
                    screenshot.image_role,
                    "AI_PRODUCT_NOT_IDENTIFIED",
                    "Image did not identify a product clearly.",
                )
            )
            continue
        successes.append((understanding, screenshot, completion.model))

    if not successes:
        draft = _create_fallback_draft(
            db,
            job,
            code="AI_MULTI_IMAGE_ANALYSIS_FAILED",
            message=VISION_PRODUCTION_FAILURE_MESSAGE,
            multi_image_summary=_multi_image_summary_for_job(
                job,
                analysis_strategy="per_image_failed",
                failed_images=fallback_failures,
            ),
        )
        return _build_screenshots_response(job, assets, draft, ai_result_type="fallback", ai_fallback_used=True)

    model_used = successes[0][2]
    merged = _merge_individual_understandings(successes, fallback_failures, source_platform)
    draft = _create_draft_from_understanding(
        db,
        job,
        understanding=merged,
        source_platform_hint=source_platform,
        evidence_image_roles=_image_role_map(job),
        manual_required_code="PARTIAL_IMAGE_ANALYSIS_FAILED" if fallback_failures else "MULTI_IMAGE_ANALYSIS_FALLBACK",
        manual_required_message="Multi-image analysis used per-image fallback and requires manual review.",
        model_used=model_used,
        multi_image_summary=_multi_image_summary_for_job(
            job,
            analysis_strategy="per_image_fallback",
            failed_images=fallback_failures,
        ),
    )
    return _build_screenshots_response(job, assets, draft, ai_result_type="manual_required", ai_fallback_used=True)


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
    evidence_image_roles: dict[int, str] | None = None,
    manual_required_code: str | None = None,
    manual_required_message: str | None = None,
    model_used: str | None = None,
    multi_image_summary: dict[str, object] | None = None,
) -> ProductDraft:
    source_platform = understanding.source_platform
    if source_platform == "unknown" and source_platform_hint != "unknown":
        source_platform = source_platform_hint

    confidence = understanding.confidence_score
    if manual_required_code and confidence >= LOW_CONFIDENCE_THRESHOLD:
        confidence = Decimal("0.6400")
    image_count, primary_image_asset_id = _image_context_for_job(job)
    if model_used:
        job.model_used = model_used
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
        evidence=_sanitize_evidence(understanding, image_roles=evidence_image_roles),
        confidence_score=confidence,
        image_count=image_count,
        primary_image_asset_id=primary_image_asset_id,
        multi_image_summary=multi_image_summary or _multi_image_summary(image_count, primary_image_asset_id),
        status="draft",
    )
    job.source_platform = source_platform
    if manual_required_code:
        job.status = "draft_ready_with_low_confidence"
        job.error_code = manual_required_code
        job.error_message = sanitize_intake_text(manual_required_message, max_length=240)
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
    job: ProductImportJob,
    *,
    code: str,
    message: str,
    model_used: str | None = None,
    multi_image_summary: dict[str, object] | None = None,
) -> ProductDraft:
    safe_message = sanitize_intake_text(message, max_length=240)
    if model_used:
        job.model_used = model_used
    job.status = "draft_ready_with_low_confidence"
    job.error_code = code
    job.error_message = safe_message
    image_count, primary_image_asset_id = _image_context_for_job(job)
    draft = ProductDraft(
        import_job_id=job.id,
        company_id=job.company_id,
        source_platform=job.source_platform,
        confidence_score=Decimal("0.0000"),
        image_count=image_count,
        primary_image_asset_id=primary_image_asset_id,
        multi_image_summary=multi_image_summary or _multi_image_summary(image_count, primary_image_asset_id),
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


def _image_context_for_job(job: ProductImportJob) -> tuple[int, int | None]:
    assets = sorted(job.assets, key=lambda asset: asset.image_index)
    if not assets:
        return 0, None
    primary = next((asset for asset in assets if asset.is_primary), assets[0])
    return len(assets), primary.id


def _multi_image_summary(image_count: int, primary_image_asset_id: int | None) -> dict[str, object] | None:
    if image_count <= 0:
        return None
    return {
        "image_count": image_count,
        "primary_image_asset_id": primary_image_asset_id,
        "analysis_strategy": "single_image",
        "failed_images": [],
        "image_roles": ["screenshot"],
        "summary": "Single uploaded screenshot captured as the primary product image.",
    }


def _multi_image_summary_for_job(
    job: ProductImportJob,
    *,
    analysis_strategy: str,
    failed_images: list[dict[str, object]] | None = None,
) -> dict[str, object] | None:
    image_count, primary_image_asset_id = _image_context_for_job(job)
    if image_count <= 0 and not failed_images:
        return None
    assets = sorted(job.assets, key=lambda asset: asset.image_index)
    return {
        "image_count": image_count,
        "primary_image_asset_id": primary_image_asset_id,
        "analysis_strategy": analysis_strategy,
        "image_roles": [sanitize_intake_text(asset.image_role, max_length=64) or "unknown" for asset in assets],
        "failed_images": failed_images or [],
        "summary": (
            "Multiple uploaded product images were analyzed as one product draft."
            if image_count != 1
            else "Single uploaded screenshot captured as the primary product image."
        ),
    }


def _image_role_map(job: ProductImportJob) -> dict[int, str]:
    return {
        int(asset.image_index): sanitize_intake_text(asset.image_role, max_length=64) or "unknown"
        for asset in sorted(job.assets, key=lambda asset: asset.image_index)
    }


def _build_screenshot_response(
    job: ProductImportJob,
    asset: ProductImportAsset,
    draft: ProductDraft,
    *,
    ai_result_type: AiResultType,
    ai_fallback_used: bool,
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
        ai_result_type=ai_result_type,
        ai_fallback_used=ai_fallback_used,
        model_used=job.model_used,
        error_code=job.error_code,
        error_message=job.error_message,
        next_action=next_action,
        asset=ProductImportAssetRead.model_validate(asset),
        draft=ProductDraftSummary.model_validate(draft),
    )


def _build_screenshots_response(
    job: ProductImportJob,
    assets: list[ProductImportAsset],
    draft: ProductDraft,
    *,
    ai_result_type: AiResultType,
    ai_fallback_used: bool,
) -> ProductScreenshotsIntakeResponse:
    ordered_assets = sorted(assets, key=lambda asset: asset.image_index)
    primary_asset = next((asset for asset in ordered_assets if asset.is_primary), ordered_assets[0])
    draft_summary = ProductDraftRead.model_validate(draft)
    next_action = "review_draft"
    if job.error_code and job.error_code != "LOW_CONFIDENCE":
        next_action = "manual_fill"
    elif draft_summary.low_confidence:
        next_action = "manual_review"
    return ProductScreenshotsIntakeResponse(
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
        asset=ProductImportAssetRead.model_validate(primary_asset),
        assets=[ProductImportAssetRead.model_validate(asset) for asset in ordered_assets],
        draft=ProductDraftSummary.model_validate(draft),
    )


def _safe_fallback_message(code: str, raw_message: str) -> str:
    safe = sanitize_intake_text(raw_message, max_length=160) or "Vision analysis failed."
    generic_by_code = {
        "BAILIAN_VISION_DISABLED": "视觉模型未启用，请人工补全商品信息。",
        "BAILIAN_VISION_MODEL_NOT_CONFIGURED": "视觉模型未配置，请配置视觉模型后再启用截图识别。",
        "BAILIAN_NOT_CONFIGURED": "Bailian API key is not configured; a manual draft was created.",
        "BAILIAN_AUTHENTICATION_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_RATE_LIMITED": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_TIMEOUT": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_UPSTREAM_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
        "BAILIAN_RESPONSE_ERROR": VISION_PRODUCTION_FAILURE_MESSAGE,
    }
    return generic_by_code.get(code, safe)


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, BailianError):
        return exc.code
    if isinstance(exc, AiJsonParseError):
        return "AI_RESPONSE_PARSE_ERROR"
    if isinstance(exc, ValidationError):
        return "AI_RESPONSE_SCHEMA_ERROR"
    return "IMAGE_ANALYSIS_FAILED"


def _merge_individual_understandings(
    successes: list[tuple[QwenProductUnderstandingResponse, StoredScreenshot, str]],
    failed_images: list[dict[str, object]],
    source_platform_hint: str,
) -> QwenProductUnderstandingResponse:
    best = max(successes, key=lambda item: item[0].confidence_score)
    best_understanding = best[0]
    scalar_fields = {
        "source_platform": best_understanding.source_platform if best_understanding.source_platform != "unknown" else source_platform_hint,
        "product_name_cn": best_understanding.product_name_cn,
        "product_name_en": best_understanding.product_name_en,
        "category": best_understanding.category,
        "price_cny": best_understanding.price_cny,
        "material": best_understanding.material,
        "specification": best_understanding.specification,
        "dimensions": best_understanding.dimensions,
        "weight_estimate": best_understanding.weight_estimate,
    }
    list_fields = {
        "color_options": _merge_text_lists([item[0].color_options for item in successes]),
        "selling_points_cn": _merge_text_lists([item[0].selling_points_cn for item in successes]),
        "selling_points_en": _merge_text_lists([item[0].selling_points_en for item in successes]),
        "target_users": _merge_text_lists([item[0].target_users for item in successes]),
        "usage_scenarios": _merge_text_lists([item[0].usage_scenarios for item in successes]),
        "cross_border_keywords_en": _merge_text_lists([item[0].cross_border_keywords_en for item in successes]),
        "risk_notes": _merge_text_lists([item[0].risk_notes for item in successes]),
    }
    risk_notes = list(list_fields["risk_notes"])
    for failure in failed_images:
        risk = sanitize_intake_text(
            f"Image {failure.get('image_index')} ({failure.get('image_role')}) requires manual review: {failure.get('code')}",
            max_length=180,
        )
        if risk:
            risk_notes.append(risk)
    list_fields["risk_notes"] = _sanitize_text_list(risk_notes)

    evidence: list[dict[str, object]] = []
    for understanding, screenshot, _model in successes:
        for item in understanding.evidence:
            evidence.append(
                {
                    "field": item.field,
                    "source": item.source,
                    "image_index": screenshot.image_index,
                    "image_role": screenshot.image_role,
                    "value": item.value,
                }
            )

    confidence = best_understanding.confidence_score
    if failed_images or len(successes) > 1:
        confidence = min(confidence, Decimal("0.6400"))
    return QwenProductUnderstandingResponse.model_validate(
        {
            **scalar_fields,
            **list_fields,
            "confidence_score": confidence,
            "evidence": evidence,
        }
    )


def _merge_text_lists(groups: list[list[str]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for values in groups:
        for value in values:
            text = sanitize_intake_text(value, max_length=180)
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            merged.append(text)
            seen.add(key)
    return merged


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


def _sanitize_evidence(
    understanding: QwenProductUnderstandingResponse,
    *,
    image_roles: dict[int, str] | None = None,
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    default_index = min(image_roles) if image_roles else 0
    default_role = image_roles.get(default_index, "screenshot") if image_roles else "screenshot"
    for item in understanding.evidence:
        image_index = item.image_index if item.image_index is not None else default_index
        if image_roles and image_index not in image_roles:
            image_index = default_index
        image_role = image_roles.get(image_index, default_role) if image_roles else (item.image_role or default_role)
        sanitized.append(
            {
                "field": sanitize_intake_text(item.field, max_length=128) or "unknown",
                "source": item.source,
                "image_index": image_index,
                "image_role": sanitize_intake_text(image_role, max_length=64) or "unknown",
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
