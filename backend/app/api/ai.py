from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    AiChatRequest,
    AiChatResponse,
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
