import base64
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas import (
    AiChatRequest,
    AiChatResponse,
    AiSmokeResponse,
    AiStatusResponse,
    MarketingCopyRequest,
    MarketingCopyResponse,
    ProductKeywordsRequest,
    ProductKeywordsResponse,
    ReportSectionRequest,
    ReportSectionResponse,
)
from app.services.ai import (
    BailianAuthenticationError,
    BailianClient,
    BailianConfigurationError,
    BailianError,
    BailianRateLimitError,
    BailianResponseError,
    BailianTimeoutError,
    BailianUpstreamError,
    AiStructuredOutputError,
    generate_product_keywords,
)
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import (
    build_marketing_copy_messages,
    build_report_section_messages,
)
from app.utils.redaction import redact_text


router = APIRouter()


def get_bailian_client() -> BailianClient:
    return BailianClient()


@router.get("/status", response_model=AiStatusResponse)
def ai_status(settings: Settings = Depends(get_settings)) -> AiStatusResponse:
    text = _status_payload(
        model=settings.bailian_model,
        configured=bool(settings.bailian_api_key),
        sanitized_error=None if settings.bailian_api_key else "BAILIAN_NOT_CONFIGURED",
    )
    vision_error = _vision_configuration_error(settings)
    vision = _status_payload(
        model=settings.bailian_vision_model,
        configured=vision_error is None,
        sanitized_error=vision_error,
    )
    return AiStatusResponse(
        model=settings.bailian_model,
        configured=text.configured,
        sanitized_error=text.sanitized_error,
        text=text,
        vision=vision,
    )


@router.post("/smoke/text", response_model=AiSmokeResponse)
async def smoke_text(client: BailianClient = Depends(get_bailian_client)) -> AiSmokeResponse:
    try:
        result = await client.chat(
            [
                {
                    "role": "system",
                    "content": "Return only JSON and do not include secrets.",
                },
                {"role": "user", "content": "Return {\"ok\": true}."},
            ],
            temperature=0.0,
            max_tokens=24,
            json_mode=True,
        )
    except BailianError as exc:
        return AiSmokeResponse(
            model=client.model_name,
            configured=not isinstance(exc, BailianConfigurationError),
            success=False,
            fallback_used=False,
            sanitized_error=exc.code,
        )

    if not result.content.strip():
        return AiSmokeResponse(
            model=result.model,
            configured=True,
            success=False,
            fallback_used=False,
            sanitized_error="EMPTY_PROVIDER_RESPONSE",
        )
    return AiSmokeResponse(
        model=result.model,
        configured=True,
        success=True,
        fallback_used=False,
        sanitized_error=None,
    )


@router.post("/smoke/vision", response_model=AiSmokeResponse)
async def smoke_vision(client: BailianClient = Depends(get_bailian_client)) -> AiSmokeResponse:
    try:
        result = await client.vision_chat(
            _build_vision_smoke_messages(),
            temperature=0.0,
            max_tokens=48,
            json_mode=True,
        )
    except BailianError as exc:
        return AiSmokeResponse(
            model=client.vision_model_name,
            configured=not isinstance(exc, BailianConfigurationError),
            success=False,
            fallback_used=False,
            sanitized_error=exc.code,
        )

    if not result.content.strip():
        return AiSmokeResponse(
            model=result.model,
            configured=True,
            success=False,
            fallback_used=False,
            sanitized_error="EMPTY_PROVIDER_RESPONSE",
        )
    return AiSmokeResponse(
        model=result.model,
        configured=True,
        success=True,
        fallback_used=False,
        sanitized_error=None,
    )


@router.post("/chat", response_model=AiChatResponse)
async def chat(payload: AiChatRequest, client: BailianClient = Depends(get_bailian_client)) -> AiChatResponse:
    try:
        result = await client.chat(
            [message.model_dump() for message in payload.messages],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            json_mode=payload.json_mode,
        )
    except BailianError as exc:
        raise _to_http_exception(exc) from exc
    return AiChatResponse(content=result.content, model=result.model, usage=result.usage)


@router.post("/product-keywords", response_model=ProductKeywordsResponse)
async def product_keywords(
    payload: ProductKeywordsRequest,
    client: BailianClient = Depends(get_bailian_client),
) -> ProductKeywordsResponse:
    try:
        return await generate_product_keywords(payload, client)
    except BailianError as exc:
        raise _to_http_exception(exc) from exc
    except AiStructuredOutputError as exc:
        raise _structured_output_exception(
            exc.code,
            exc.message,
            errors=exc.errors,
        ) from exc


@router.post("/marketing-copy", response_model=MarketingCopyResponse)
async def marketing_copy(
    payload: MarketingCopyRequest,
    client: BailianClient = Depends(get_bailian_client),
) -> MarketingCopyResponse:
    messages = build_marketing_copy_messages(payload.model_dump(mode="json", exclude_none=True))
    try:
        result = await client.chat(messages, temperature=0.7, max_tokens=1400, json_mode=True)
        parsed = parse_json_object(result.content)
        return MarketingCopyResponse.model_validate(parsed)
    except BailianError as exc:
        raise _to_http_exception(exc) from exc
    except AiJsonParseError as exc:
        raise _structured_output_exception("AI_RESPONSE_PARSE_ERROR", "AI response was not valid structured JSON.") from exc
    except ValidationError as exc:
        raise _structured_output_exception(
            "AI_RESPONSE_SCHEMA_ERROR",
            "AI response JSON did not match expected marketing copy schema.",
            errors=_safe_validation_errors(exc),
        ) from exc


@router.post("/report-section", response_model=ReportSectionResponse)
async def report_section(
    payload: ReportSectionRequest,
    client: BailianClient = Depends(get_bailian_client),
) -> ReportSectionResponse:
    messages = build_report_section_messages(payload.model_dump(mode="json", exclude_none=True))
    try:
        result = await client.chat(messages, temperature=0.5, max_tokens=1600, json_mode=True)
        parsed = parse_json_object(result.content)
        return ReportSectionResponse.model_validate(parsed)
    except BailianError as exc:
        raise _to_http_exception(exc) from exc
    except AiJsonParseError as exc:
        raise _structured_output_exception("AI_RESPONSE_PARSE_ERROR", "AI response was not valid structured JSON.") from exc
    except ValidationError as exc:
        raise _structured_output_exception(
            "AI_RESPONSE_SCHEMA_ERROR",
            "AI response JSON did not match expected report section schema.",
            errors=_safe_validation_errors(exc),
        ) from exc


def _to_http_exception(exc: BailianError) -> HTTPException:
    if isinstance(exc, BailianConfigurationError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, BailianTimeoutError):
        http_status = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, BailianRateLimitError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, BailianAuthenticationError):
        http_status = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, (BailianUpstreamError, BailianResponseError)):
        http_status = status.HTTP_502_BAD_GATEWAY
    else:
        http_status = status.HTTP_502_BAD_GATEWAY

    return HTTPException(
        status_code=http_status,
        detail={
            "code": exc.code,
            "message": redact_text(str(exc)),
            "provider": "bailian",
        },
    )


def _status_payload(
    *,
    model: str | None,
    configured: bool,
    sanitized_error: str | None,
) -> AiSmokeResponse:
    return AiSmokeResponse(
        model=model,
        configured=configured,
        success=False,
        fallback_used=False,
        sanitized_error=sanitized_error,
    )


def _vision_configuration_error(settings: Settings) -> str | None:
    if not settings.bailian_vision_enabled:
        return "BAILIAN_VISION_DISABLED"
    if not settings.bailian_vision_model:
        return "BAILIAN_VISION_MODEL_NOT_CONFIGURED"
    if not settings.bailian_api_key:
        return "BAILIAN_NOT_CONFIGURED"
    return None


def _build_vision_smoke_messages() -> list[dict[str, object]]:
    image_data_url = f"data:image/png;base64,{_small_png_base64()}"
    return [
        {"role": "system", "content": "Return only JSON. Do not include secrets."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "This is a smoke test image. Return {\"ok\": true}."},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _small_png_base64() -> str:
    buffer = BytesIO()
    image = Image.new("RGB", (4, 4), color=(40, 120, 200))
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _structured_output_exception(
    code: str,
    message: str,
    *,
    errors: list[dict[str, object]] | None = None,
) -> HTTPException:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
        "provider": "bailian",
    }
    if errors is not None:
        detail["errors"] = errors
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
