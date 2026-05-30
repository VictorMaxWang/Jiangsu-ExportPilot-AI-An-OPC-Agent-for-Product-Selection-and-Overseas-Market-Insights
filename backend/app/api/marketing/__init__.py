from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.ai import get_bailian_client
from app.db import get_db
from app.schemas import MarketingGenerateRequest, MarketingGenerateResponse
from app.services.ai import (
    BailianAuthenticationError,
    BailianClient,
    BailianConfigurationError,
    BailianError,
    BailianRateLimitError,
    BailianResponseError,
    BailianTimeoutError,
    BailianUpstreamError,
)
from app.services.marketing import (
    MarketingGenerationInputError,
    MarketingGenerationOutputError,
    MarketingGenerator,
)
from app.utils.redaction import redact_mapping, redact_text


router = APIRouter()


def get_marketing_generator(
    db: Session = Depends(get_db),
    ai_client: BailianClient = Depends(get_bailian_client),
) -> MarketingGenerator:
    return MarketingGenerator(db, ai_client=ai_client)


@router.post("/generate", response_model=MarketingGenerateResponse)
async def generate_marketing(
    request: MarketingGenerateRequest,
    service: MarketingGenerator = Depends(get_marketing_generator),
) -> MarketingGenerateResponse:
    try:
        return await service.generate(request)
    except MarketingGenerationInputError as exc:
        raise _input_exception(exc) from exc
    except MarketingGenerationOutputError as exc:
        raise _output_exception(exc) from exc
    except BailianError as exc:
        raise _bailian_exception(exc) from exc


def _input_exception(exc: MarketingGenerationInputError) -> HTTPException:
    if exc.code in {"ANALYSIS_NOT_FOUND", "SCORE_NOT_FOUND"}:
        http_status = status.HTTP_404_NOT_FOUND
    else:
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(
        status_code=http_status,
        detail={"code": exc.code, "message": redact_text(str(exc))},
    )


def _output_exception(exc: MarketingGenerationOutputError) -> HTTPException:
    detail: dict[str, object] = {
        "code": exc.code,
        "message": redact_text(str(exc)),
        "provider": "bailian",
    }
    if exc.errors is not None:
        detail["errors"] = redact_mapping(exc.errors)
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _bailian_exception(exc: BailianError) -> HTTPException:
    if isinstance(exc, BailianConfigurationError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        message = "Bailian is not configured on the backend. Set DASHSCOPE_API_KEY."
    elif isinstance(exc, BailianTimeoutError):
        http_status = status.HTTP_504_GATEWAY_TIMEOUT
        message = redact_text(str(exc))
    elif isinstance(exc, BailianRateLimitError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        message = redact_text(str(exc))
    elif isinstance(exc, BailianAuthenticationError):
        http_status = status.HTTP_502_BAD_GATEWAY
        message = redact_text(str(exc))
    elif isinstance(exc, (BailianUpstreamError, BailianResponseError)):
        http_status = status.HTTP_502_BAD_GATEWAY
        message = redact_text(str(exc))
    else:
        http_status = status.HTTP_502_BAD_GATEWAY
        message = "Bailian request failed."

    return HTTPException(
        status_code=http_status,
        detail={
            "code": exc.code,
            "message": message,
            "provider": "bailian",
        },
    )
