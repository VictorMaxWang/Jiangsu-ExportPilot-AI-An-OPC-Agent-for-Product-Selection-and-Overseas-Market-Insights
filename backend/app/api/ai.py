import base64
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas import (
    AiChatRequest,
    AiChatResponse,
    AiErrorStage,
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

VISION_SMOKE_RESPONSE_INVALID = "VISION_SMOKE_RESPONSE_INVALID"


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
        return _smoke_error_response(client.model_name, exc, vision=False)

    if not result.content.strip():
        return AiSmokeResponse(
            model=result.model,
            configured=True,
            success=False,
            fallback_used=False,
            sanitized_error="EMPTY_PROVIDER_RESPONSE",
            error_stage="response_parse",
            suggested_action="Retry the text smoke; if it repeats, check the configured Bailian text model response format.",
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
        return _smoke_error_response(client.vision_model_name, exc, vision=True)

    validation_error = _validate_vision_smoke_content(result.content)
    if validation_error is not None:
        return _validation_error_for_vision_smoke(result.model, validation_error)
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
    error_stage, suggested_action = _configuration_diagnostics(sanitized_error)
    return AiSmokeResponse(
        model=model,
        configured=configured,
        success=False,
        fallback_used=False,
        sanitized_error=sanitized_error,
        error_stage=error_stage,
        suggested_action=suggested_action,
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
                {
                    "type": "text",
                    "text": "Inspect this smoke test image and return exactly {\"ok\": true, \"image_seen\": true}.",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _small_png_base64() -> str:
    buffer = BytesIO()
    image = Image.new("RGB", (32, 32), color=(40, 120, 200))
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _smoke_error_response(model: str | None, exc: BailianError, *, vision: bool) -> AiSmokeResponse:
    return AiSmokeResponse(
        model=model,
        configured=not isinstance(exc, BailianConfigurationError),
        success=False,
        fallback_used=False,
        sanitized_error=exc.code,
        error_stage=_error_stage_for_exception(exc),
        upstream_status_code=exc.status_code,
        suggested_action=_suggested_action_for_exception(exc, vision=vision),
    )


def _error_stage_for_exception(exc: BailianError) -> AiErrorStage:
    stage = getattr(exc, "error_stage", "unknown")
    if stage in {
        "request_build",
        "upstream_http",
        "response_parse",
        "model_not_available",
        "unsupported_input",
        "unknown",
    }:
        return stage
    return "unknown"


def _validate_vision_smoke_content(content: str) -> str | None:
    if not content.strip():
        return "EMPTY_PROVIDER_RESPONSE"
    try:
        parsed = parse_json_object(content)
    except AiJsonParseError:
        return "AI_RESPONSE_PARSE_ERROR"
    if parsed.get("ok") is not True or parsed.get("image_seen") is not True:
        return VISION_SMOKE_RESPONSE_INVALID
    return None


def _validation_error_for_vision_smoke(model: str, sanitized_error: str) -> AiSmokeResponse:
    return AiSmokeResponse(
        model=model,
        configured=True,
        success=False,
        fallback_used=False,
        sanitized_error=sanitized_error,
        error_stage="response_parse",
        suggested_action=(
            "Check that BAILIAN_VISION_MODEL supports image understanding through the OpenAI-compatible "
            "chat completions image_url data URL format."
        ),
    )


def _configuration_diagnostics(sanitized_error: str | None) -> tuple[AiErrorStage | None, str | None]:
    if sanitized_error is None:
        return None, None
    if sanitized_error in {"BAILIAN_NOT_CONFIGURED", "BAILIAN_VISION_DISABLED", "BAILIAN_VISION_MODEL_NOT_CONFIGURED"}:
        return "request_build", _suggested_action_for_code(sanitized_error, vision=True)
    return "unknown", None


def _suggested_action_for_exception(exc: BailianError, *, vision: bool) -> str:
    if vision:
        vision_action = _suggested_action_for_vision_exception(exc)
        if vision_action is not None:
            return vision_action
    return _suggested_action_for_code(exc.code, vision=vision)


def _suggested_action_for_vision_exception(exc: BailianError) -> str | None:
    upstream_code = str(getattr(exc, "upstream_code", "") or "")
    normalized = upstream_code.casefold()
    if exc.status_code == 404 or "modelnotfound" in normalized or "model_not_found" in normalized:
        return (
            "BAILIAN_VISION_MODEL appears unavailable or misspelled for this Bailian/DashScope account and "
            "region; choose a valid vision model in the environment and restart the backend."
        )
    if exc.status_code == 401:
        return "Check the backend DashScope credential without exposing it, then restart the backend and rerun vision smoke."
    if exc.status_code == 403 or "accessdenied" in normalized or "forbidden" in normalized:
        return (
            "The DashScope account or workspace is not authorized for this vision model; enable Bailian vision "
            "model access or grant model invocation permission in the console."
        )
    if "model_not_supported" in normalized or "notcompatible" in normalized:
        return (
            "OpenAI-compatible chat completions does not support this vision model/method combination; run the "
            "backend probe and use DashScope native multimodal if that method succeeds."
        )
    if "unsupported" in normalized:
        return (
            "The configured vision model rejected this input shape or method; verify OpenAI-compatible image_url "
            "support and try DashScope native multimodal if needed."
        )
    if exc.status_code == 400:
        return (
            "OpenAI-compatible request payload must use a supported image size and format; the vision smoke image "
            "must be wider and taller than 10px. If 400 persists after the 32x32 smoke fix, check "
            "BAILIAN_VISION_MODEL and try DashScope native multimodal."
        )
    return None


def _suggested_action_for_code(code: str, *, vision: bool) -> str:
    suggestions = {
        "BAILIAN_NOT_CONFIGURED": "Set the backend DashScope credential in the runtime environment and restart the service.",
        "BAILIAN_VISION_DISABLED": "Set BAILIAN_VISION_ENABLED=true only after configuring a valid Bailian vision model.",
        "BAILIAN_VISION_MODEL_NOT_CONFIGURED": "Set BAILIAN_VISION_MODEL to a Bailian Qwen-VL model ID available to this account and region.",
        "BAILIAN_AUTHENTICATION_ERROR": "Check the backend DashScope credential permissions without exposing the credential.",
        "BAILIAN_RATE_LIMITED": "Retry later or reduce smoke frequency; keep the configured model unchanged.",
        "BAILIAN_TIMEOUT": "Retry later and check network connectivity to Bailian/DashScope.",
        "BAILIAN_RESPONSE_ERROR": "Check whether the configured model returns OpenAI-compatible chat completion JSON.",
    }
    if code == "BAILIAN_UPSTREAM_ERROR" and vision:
        return (
            "Check BAILIAN_VISION_MODEL availability for the current account and region, then run the safe "
            "Bailian vision probe to compare OpenAI-compatible and DashScope native multimodal methods."
        )
    if code == "BAILIAN_UPSTREAM_ERROR":
        return "Check Bailian service availability and the configured text model ID."
    return suggestions.get(code, "Review backend Bailian configuration and retry the smoke check.")


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
