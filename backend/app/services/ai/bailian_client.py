from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class BailianError(Exception):
    """Base error for sanitized Bailian client failures."""

    code = "BAILIAN_ERROR"
    error_stage = "unknown"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        upstream_code: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.upstream_code = upstream_code
        if error_stage is not None:
            self.error_stage = error_stage


class BailianConfigurationError(BailianError):
    code = "BAILIAN_NOT_CONFIGURED"
    error_stage = "request_build"


class BailianVisionDisabledError(BailianConfigurationError):
    code = "BAILIAN_VISION_DISABLED"


class BailianVisionModelNotConfiguredError(BailianConfigurationError):
    code = "BAILIAN_VISION_MODEL_NOT_CONFIGURED"


class BailianAuthenticationError(BailianError):
    code = "BAILIAN_AUTHENTICATION_ERROR"
    error_stage = "upstream_http"


class BailianRateLimitError(BailianError):
    code = "BAILIAN_RATE_LIMITED"
    error_stage = "upstream_http"


class BailianTimeoutError(BailianError):
    code = "BAILIAN_TIMEOUT"
    error_stage = "upstream_http"


class BailianUpstreamError(BailianError):
    code = "BAILIAN_UPSTREAM_ERROR"
    error_stage = "upstream_http"


class BailianResponseError(BailianError):
    code = "BAILIAN_RESPONSE_ERROR"
    error_stage = "response_parse"


@dataclass(frozen=True)
class BailianChatCompletion:
    content: str
    model: str
    usage: dict[str, Any] | None = None


class BailianClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport

    @property
    def model_name(self) -> str:
        return self._settings.bailian_model

    @property
    def vision_model_name(self) -> str | None:
        return self._settings.bailian_vision_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> BailianChatCompletion:
        return await self._chat_completion(
            messages,
            model=self._settings.bailian_model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def vision_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1800,
        json_mode: bool = True,
    ) -> BailianChatCompletion:
        if not self._settings.bailian_vision_enabled:
            raise BailianVisionDisabledError("Bailian vision analysis is disabled.")
        if not self._settings.bailian_vision_model:
            raise BailianVisionModelNotConfiguredError("Bailian vision model is not configured.")
        return await self._chat_completion(
            messages,
            model=self._settings.bailian_vision_model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def _chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> BailianChatCompletion:
        api_key = self._settings.bailian_api_key
        if not api_key:
            raise BailianConfigurationError("Bailian API key is not configured on backend.")

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self._settings.bailian_base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(
            self._settings.bailian_timeout_seconds,
            connect=5.0,
            read=self._settings.bailian_timeout_seconds,
            write=10.0,
            pool=5.0,
        )

        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            response = await self._post_with_retries(client, endpoint, headers, payload)

        return self._parse_chat_completion(response, fallback_model=model)

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        max_retries = max(0, self._settings.bailian_max_retries)
        attempts = max_retries + 1

        for attempt in range(attempts):
            try:
                response = await client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                if attempt < max_retries:
                    await self._sleep_before_retry(attempt)
                    continue
                raise BailianTimeoutError("Bailian request timed out.") from exc
            except httpx.HTTPError as exc:
                if attempt < max_retries:
                    await self._sleep_before_retry(attempt)
                    continue
                raise BailianUpstreamError("Bailian request failed before receiving a response.") from exc

            if response.status_code in {429} or 500 <= response.status_code <= 599:
                if attempt < max_retries:
                    await self._sleep_before_retry(attempt)
                    continue
            self._raise_for_status(response)
            return response

        raise BailianUpstreamError("Bailian request failed after retries.")

    async def _sleep_before_retry(self, attempt: int) -> None:
        await asyncio.sleep(0.1 * (attempt + 1))

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if status_code < 400:
            return
        upstream_code = _safe_upstream_error_code(response)
        if status_code in {401, 403}:
            raise BailianAuthenticationError(
                "Bailian authentication failed.",
                status_code=status_code,
                upstream_code=upstream_code,
            )
        if status_code == 429:
            raise BailianRateLimitError(
                "Bailian service rate limit reached.",
                status_code=status_code,
                upstream_code=upstream_code,
            )
        raise BailianUpstreamError(
            "Bailian service returned an upstream error.",
            status_code=status_code,
            upstream_code=upstream_code,
            error_stage=_diagnostic_stage_for_http_error(status_code, upstream_code),
        )

    def _parse_chat_completion(self, response: httpx.Response, *, fallback_model: str) -> BailianChatCompletion:
        try:
            data = response.json()
        except ValueError as exc:
            raise BailianResponseError("Bailian response was not valid JSON.") from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BailianResponseError("Bailian response did not match chat completions format.") from exc

        if not isinstance(content, str):
            raise BailianResponseError("Bailian response content was not text.")

        model = data.get("model") or fallback_model
        usage = data.get("usage")
        return BailianChatCompletion(
            content=content,
            model=str(model),
            usage=usage if isinstance(usage, dict) else None,
        )


_SAFE_UPSTREAM_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


def _safe_upstream_error_code(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    nested_error = data.get("error")
    candidates: list[object] = [
        data.get("code"),
        data.get("type"),
        data.get("status_name"),
    ]
    if isinstance(nested_error, dict):
        candidates.extend(
            [
                nested_error.get("code"),
                nested_error.get("type"),
            ]
        )

    for candidate in candidates:
        if isinstance(candidate, str):
            value = candidate.strip()
            if _SAFE_UPSTREAM_CODE_RE.fullmatch(value):
                return value
    return None


def _diagnostic_stage_for_http_error(status_code: int, upstream_code: str | None) -> str:
    normalized = (upstream_code or "").casefold()
    if status_code == 404 or "modelnotfound" in normalized or "model_not_found" in normalized:
        return "model_not_available"
    if "notcompatible" in normalized or "not_supported" in normalized or "unsupported" in normalized:
        return "unsupported_input"
    if status_code == 400:
        return "unsupported_input"
    return "upstream_http"
