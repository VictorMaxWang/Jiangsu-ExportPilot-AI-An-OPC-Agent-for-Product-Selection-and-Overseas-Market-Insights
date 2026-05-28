from __future__ import annotations

from pydantic import ValidationError

from app.schemas.ai import ProductKeywordsRequest, ProductKeywordsResponse
from app.services.ai.bailian_client import BailianClient
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_product_keyword_messages


class AiStructuredOutputError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.errors = errors
        super().__init__(message)


async def generate_product_keywords(
    payload: ProductKeywordsRequest,
    client: BailianClient,
) -> ProductKeywordsResponse:
    messages = build_product_keyword_messages(payload.model_dump(mode="json", exclude_none=True))
    result = await client.chat(messages, temperature=0.2, max_tokens=1200, json_mode=True)
    try:
        parsed = parse_json_object(result.content)
        return ProductKeywordsResponse.model_validate(parsed)
    except AiJsonParseError as exc:
        raise AiStructuredOutputError(
            "AI_RESPONSE_PARSE_ERROR",
            "AI response was not valid structured JSON.",
        ) from exc
    except ValidationError as exc:
        raise AiStructuredOutputError(
            "AI_RESPONSE_SCHEMA_ERROR",
            "AI response JSON did not match expected product keyword schema.",
            errors=_safe_validation_errors(exc),
        ) from exc


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
