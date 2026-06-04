from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from app.core.config import get_settings


DEFAULT_QWEN_TIMEOUT_SECONDS = 30.0

T = TypeVar("T")


def qwen_timeout_seconds() -> float:
    value = float(get_settings().bailian_timeout_seconds or DEFAULT_QWEN_TIMEOUT_SECONDS)
    return value if value > 0 else DEFAULT_QWEN_TIMEOUT_SECONDS


async def wait_for_qwen(
    awaitable: Awaitable[T],
    *,
    timeout_seconds: float | None = None,
) -> T:
    timeout = timeout_seconds if timeout_seconds is not None else qwen_timeout_seconds()
    return await asyncio.wait_for(awaitable, timeout=timeout)
