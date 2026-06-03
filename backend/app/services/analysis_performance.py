from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterator, TypeVar


MAX_PERFORMANCE_EVENTS = 1000
PROVIDER_EVENT_TYPES = {"provider", "provider_http"}
QWEN_EVENT_TYPE = "qwen"

_current_recorder: ContextVar[AnalysisPerformanceRecorder | None] = ContextVar(
    "analysis_performance_recorder",
    default=None,
)
_current_step_id: ContextVar[str | None] = ContextVar("analysis_performance_step_id", default=None)

T = TypeVar("T")


@dataclass
class AnalysisPerformanceRecorder:
    state: dict[str, Any]
    max_events: int = MAX_PERFORMANCE_EVENTS

    def ensure_payload(self) -> dict[str, Any]:
        payload = self.state.setdefault("performance", {})
        if not isinstance(payload, dict):
            payload = {}
            self.state["performance"] = payload
        events = payload.setdefault("events", [])
        if not isinstance(events, list):
            payload["events"] = []
        payload.setdefault("truncated_event_count", 0)
        return payload

    def record(self, event: dict[str, Any]) -> None:
        payload = self.ensure_payload()
        events = payload.setdefault("events", [])
        if not isinstance(events, list):
            events = []
            payload["events"] = events
        safe_event = _safe_event(event)
        if len(events) < self.max_events:
            events.append(safe_event)
            return
        payload["truncated_event_count"] = int(payload.get("truncated_event_count") or 0) + 1

    def mark_latest_qwen_fallback(self, reason: str) -> bool:
        step_id = _current_step_id.get()
        payload = self.ensure_payload()
        events = payload.get("events")
        if not isinstance(events, list):
            return False
        for event in reversed(events):
            if not isinstance(event, dict):
                continue
            if event.get("type") != QWEN_EVENT_TYPE:
                continue
            if step_id is not None and event.get("step_id") != step_id:
                continue
            event["fallback_used"] = True
            event["fallback_reason"] = _safe_label(reason, 80)
            if event.get("status") == "success":
                event["status"] = "fallback"
            return True
        return False


class PerformanceBailianClient:
    """Small proxy that records Qwen call timing without touching prompts or headers."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def model_name(self) -> str:
        return str(getattr(self._client, "model_name", "") or "")

    @property
    def vision_model_name(self) -> str | None:
        value = getattr(self._client, "vision_model_name", None)
        return str(value) if value else None

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> Any:
        return await self._recorded_qwen_call(
            "chat",
            self._client.chat,
            messages,
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
    ) -> Any:
        return await self._recorded_qwen_call(
            "vision_chat",
            self._client.vision_chat,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def _recorded_qwen_call(
        self,
        operation: str,
        call: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        started_at = _utc_now()
        start = perf_counter()
        model = self.vision_model_name if operation == "vision_chat" else self.model_name
        json_mode = bool(kwargs.get("json_mode", False))
        try:
            result = await call(*args, **kwargs)
        except Exception as exc:
            timeout = is_timeout_error(exc)
            record_qwen_call(
                operation=operation,
                model=model,
                status="timeout" if timeout else "error",
                started_at=started_at,
                duration_ms=_elapsed_ms(start),
                json_mode=json_mode,
                timeout=timeout,
                fallback_used=False,
            )
            raise

        record_qwen_call(
            operation=operation,
            model=str(getattr(result, "model", None) or model or ""),
            status="success",
            started_at=started_at,
            duration_ms=_elapsed_ms(start),
            json_mode=json_mode,
            timeout=False,
            fallback_used=False,
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


@contextmanager
def analysis_performance_scope(
    recorder: AnalysisPerformanceRecorder,
    step_id: str,
) -> Iterator[None]:
    recorder_token = _current_recorder.set(recorder)
    step_token = _current_step_id.set(step_id)
    try:
        yield
    finally:
        _current_step_id.reset(step_token)
        _current_recorder.reset(recorder_token)


def record_provider_call(
    *,
    provider: str,
    endpoint: str,
    status: str,
    started_at: datetime,
    duration_ms: int,
    cache_hit: bool = False,
    fallback_used: bool = False,
    timeout: bool = False,
    country: str | None = None,
) -> None:
    _record_current(
        {
            "type": "provider",
            "provider": provider,
            "endpoint": endpoint,
            "status": status,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": duration_ms,
            "cache_hit": cache_hit,
            "fallback_used": fallback_used,
            "timeout": timeout,
            "country": country,
        }
    )


def record_provider_http_call(
    *,
    provider: str,
    endpoint: str,
    status: str,
    started_at: datetime,
    duration_ms: int,
    timeout: bool = False,
    country: str | None = None,
    year: int | None = None,
    auth_mode: str | None = None,
    http_status: int | None = None,
) -> None:
    _record_current(
        {
            "type": "provider_http",
            "provider": provider,
            "endpoint": endpoint,
            "status": status,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": duration_ms,
            "cache_hit": False,
            "fallback_used": False,
            "timeout": timeout,
            "country": country,
            "year": year,
            "auth_mode": auth_mode,
            "http_status": http_status,
        }
    )


def record_qwen_call(
    *,
    operation: str,
    model: str | None,
    status: str,
    started_at: datetime,
    duration_ms: int,
    json_mode: bool,
    timeout: bool,
    fallback_used: bool,
) -> None:
    _record_current(
        {
            "type": QWEN_EVENT_TYPE,
            "provider": "bailian",
            "endpoint": operation,
            "model": model,
            "status": status,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "duration_ms": duration_ms,
            "json_mode": json_mode,
            "cache_hit": False,
            "fallback_used": fallback_used,
            "timeout": timeout,
        }
    )


def mark_latest_qwen_fallback(reason: str) -> None:
    recorder = _current_recorder.get()
    if recorder is not None:
        recorder.mark_latest_qwen_fallback(reason)


def get_performance_events(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    performance = (state or {}).get("performance")
    if not isinstance(performance, dict):
        return []
    events = performance.get("events")
    if not isinstance(events, list):
        return []
    return [dict(event) for event in events if isinstance(event, dict)]


def get_truncated_event_count(state: dict[str, Any] | None) -> int:
    performance = (state or {}).get("performance")
    if not isinstance(performance, dict):
        return 0
    try:
        return int(performance.get("truncated_event_count") or 0)
    except (TypeError, ValueError):
        return 0


def step_performance_counts(state: dict[str, Any] | None, step_id: str) -> dict[str, int]:
    events = [event for event in get_performance_events(state) if event.get("step_id") == step_id]
    provider_events = [event for event in events if event.get("type") in PROVIDER_EVENT_TYPES]
    qwen_events = [event for event in events if event.get("type") == QWEN_EVENT_TYPE]
    return {
        "provider_call_count": len(provider_events),
        "qwen_call_count": len(qwen_events),
        "timeout_count": sum(1 for event in events if _event_bool(event, "timeout") or event.get("status") == "timeout"),
        "cache_hit_count": sum(1 for event in events if _event_bool(event, "cache_hit")),
        "fallback_count": sum(
            1 for event in events if _event_bool(event, "fallback_used") or event.get("status") == "fallback"
        ),
    }


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    return "timeout" in exc.__class__.__name__.casefold()


def _record_current(event: dict[str, Any]) -> None:
    recorder = _current_recorder.get()
    if recorder is None:
        return
    step_id = _current_step_id.get()
    if step_id is not None:
        event["step_id"] = step_id
    recorder.record(event)


def _safe_event(event: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {
        "type": _safe_label(event.get("type"), 32),
        "step_id": _safe_label(event.get("step_id"), 128) if event.get("step_id") is not None else None,
        "provider": _safe_label(event.get("provider"), 64) if event.get("provider") is not None else None,
        "endpoint": _safe_label(event.get("endpoint"), 128) if event.get("endpoint") is not None else None,
        "status": _safe_label(event.get("status"), 32),
        "started_at": _safe_datetime(event.get("started_at")),
        "finished_at": _safe_datetime(event.get("finished_at")),
        "duration_ms": _safe_int(event.get("duration_ms")),
        "cache_hit": bool(event.get("cache_hit")),
        "fallback_used": bool(event.get("fallback_used")),
        "timeout": bool(event.get("timeout")),
    }
    for key, limit in (
        ("country", 8),
        ("auth_mode", 24),
        ("model", 96),
        ("fallback_reason", 80),
    ):
        value = event.get(key)
        if value is not None:
            safe[key] = _safe_label(value, limit)
    for key in ("year", "http_status"):
        value = event.get(key)
        if value is not None:
            safe[key] = _safe_int(value)
    if event.get("json_mode") is not None:
        safe["json_mode"] = bool(event.get("json_mode"))
    return {key: value for key, value in safe.items() if value is not None}


def _safe_label(value: object, limit: int) -> str:
    text = "".join(ch if ch.isalnum() or ch in "._:-/" else "_" for ch in str(value or "").strip())
    return (text or "unknown")[:limit]


def _safe_datetime(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value[:64]
    return None


def _safe_int(value: object) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _event_bool(event: dict[str, Any], key: str) -> bool:
    return event.get(key) is True


def _elapsed_ms(start: float) -> int:
    return max(0, round((perf_counter() - start) * 1000))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
