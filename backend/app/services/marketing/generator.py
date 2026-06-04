from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import AnalysisRun, OpportunityScore
from app.schemas import MarketingGenerateRequest, MarketingGenerateResponse
from app.services.ai import BailianClient
from app.services.ai.json_parser import AiJsonParseError, parse_json_object
from app.services.ai.prompts import build_marketing_generation_messages
from app.services.ai.qwen_timeout import wait_for_qwen


class MarketingGenerationInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class MarketingGenerationOutputError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> None:
        self.code = code
        self.errors = errors
        super().__init__(message)


class MarketingGenerator:
    def __init__(self, db: Session, *, ai_client: BailianClient | None = None) -> None:
        self._db = db
        self._ai_client = ai_client or BailianClient()

    async def generate(self, request: MarketingGenerateRequest) -> MarketingGenerateResponse:
        analysis_run = self._analysis_run(request.analysis_id)
        score = self._score_row(request)
        payload = self._prompt_payload(request, score)
        try:
            result = await wait_for_qwen(
                self._ai_client.chat(
                    build_marketing_generation_messages(payload),
                    temperature=0.5,
                    max_tokens=1400,
                    json_mode=True,
                )
            )
        except TimeoutError as exc:
            raise MarketingGenerationOutputError(
                "AI_RESPONSE_TIMEOUT",
                "Bailian marketing generation timed out.",
            ) from exc
        response = self._response_from_content(result.content)
        if request.persist_to_analysis:
            if analysis_run is None:
                raise MarketingGenerationInputError(
                    "ANALYSIS_ID_REQUIRED_FOR_PERSISTENCE",
                    "analysis_id is required when persist_to_analysis is true.",
                )
            self._persist_asset(analysis_run, request, response)
        return response

    def _analysis_run(self, analysis_id: int | None) -> AnalysisRun | None:
        if analysis_id is None:
            return None
        analysis_run = self._db.get(AnalysisRun, analysis_id)
        if analysis_run is None:
            raise MarketingGenerationInputError("ANALYSIS_NOT_FOUND", "Analysis run not found.")
        return analysis_run

    def _score_row(self, request: MarketingGenerateRequest) -> OpportunityScore | None:
        if request.score_id is None:
            return None
        score = self._db.get(OpportunityScore, request.score_id)
        if score is None:
            raise MarketingGenerationInputError("SCORE_NOT_FOUND", "Opportunity score not found.")
        if request.analysis_id is not None and score.analysis_id != request.analysis_id:
            raise MarketingGenerationInputError(
                "SCORE_ANALYSIS_MISMATCH",
                "Opportunity score does not belong to the requested analysis run.",
            )
        if score.country.strip().upper() != request.country:
            raise MarketingGenerationInputError(
                "SCORE_COUNTRY_MISMATCH",
                "Opportunity score country does not match the marketing request country.",
            )
        return score

    def _prompt_payload(
        self,
        request: MarketingGenerateRequest,
        score: OpportunityScore | None,
    ) -> dict[str, Any]:
        score_context: dict[str, Any] = {}
        if score is not None:
            score_context = {
                "reason": score.reason,
                "risk": score.risk,
                "next_action": score.next_action,
                "competitor_analysis": score.competitor_analysis or {},
                "evidence": _selected_evidence(score.evidence or {}),
                "source_note": "Use score context only as market opportunity support, not as a sales forecast.",
            }

        return {
            "product": request.product,
            "country": request.country,
            "target_users": request.target_users,
            "selling_points": request.selling_points,
            "price_range": request.price_range,
            "content_themes": request.content_themes,
            "risk_notes": request.risk_notes,
            "score_context": score_context,
            "output_policy": {
                "language": "English",
                "bullet_points": "exactly 5",
                "allowed_positioning": [
                    "market opportunity",
                    "content direction",
                    "sample data analysis",
                    "buyer pain point signals",
                    "draft for review",
                ],
                "prohibited_claims": [
                    "sales forecast",
                    "sales prediction",
                    "profit forecast",
                    "GMV forecast",
                    "guaranteed conversion",
                    "bestseller prediction",
                    "invented certification",
                    "customs or tariff certainty",
                ],
            },
        }

    def _response_from_content(self, content: str) -> MarketingGenerateResponse:
        try:
            parsed = parse_json_object(content)
            return MarketingGenerateResponse.model_validate(parsed)
        except AiJsonParseError as exc:
            raise MarketingGenerationOutputError(
                "AI_RESPONSE_PARSE_ERROR",
                "Bailian response was not valid structured marketing JSON.",
            ) from exc
        except ValidationError as exc:
            raise MarketingGenerationOutputError(
                "AI_RESPONSE_SCHEMA_ERROR",
                "Bailian response JSON did not match the expected marketing schema.",
                errors=_safe_validation_errors(exc),
            ) from exc
        except ValueError as exc:
            raise MarketingGenerationOutputError(
                "AI_RESPONSE_POLICY_ERROR",
                "Bailian response contained unsafe marketing claims.",
            ) from exc

    def _persist_asset(
        self,
        analysis_run: AnalysisRun,
        request: MarketingGenerateRequest,
        response: MarketingGenerateResponse,
    ) -> None:
        state = dict(analysis_run.workflow_state or {})
        assets = [
            dict(asset)
            for asset in state.get("marketing_assets", [])
            if isinstance(asset, dict)
        ]
        record = {
            **response.model_dump(mode="json"),
            "product": request.product,
            "country": request.country,
            "score_id": request.score_id,
            "source": "api/marketing/generate",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        record_key = _asset_key(record)
        replaced = False
        for index, asset in enumerate(assets):
            if _asset_key(asset) == record_key:
                assets[index] = record
                replaced = True
                break
        if not replaced:
            assets.append(record)

        state["marketing_assets"] = assets
        analysis_run.workflow_state = state
        flag_modified(analysis_run, "workflow_state")
        self._db.commit()


def _selected_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key in (
        "keyword",
        "competitor_sources",
        "competitor_fallback_used",
        "content_sources",
        "content_fallback_used",
        "trade_fallback_used",
        "deterministic_risks",
    ):
        if key in evidence:
            selected[key] = evidence[key]
    return selected


def _asset_key(asset: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(asset.get("product") or asset.get("product_id") or "").casefold(),
        str(asset.get("country") or "").upper(),
        str(asset.get("score_id") or ""),
    )


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
