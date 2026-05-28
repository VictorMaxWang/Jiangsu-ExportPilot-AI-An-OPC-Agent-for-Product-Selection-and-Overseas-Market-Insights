from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[REDACTED]"

_SENSITIVE_FIELD_MARKERS = (
    "dashscopeapikey",
    "youtubedataapikey",
    "etsykeystring",
    "etsysharedsecret",
    "uncomtradeapikey",
    "adminpassword",
    "authorization",
    "apikey",
    "xapikey",
    "keystring",
    "subscriptionkey",
    "clientsecret",
    "sharedsecret",
    "secret",
    "password",
    "cookie",
)
_SENSITIVE_TOKEN_FIELDS = {"token", "accesstoken", "refreshtoken", "bearertoken"}

_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(Authorization\s*[:=]\s*)(?:Bearer|Basic)?\s*[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)((?:x-api-key|subscription-key|api[_ -]?key|token|secret|password)\s*[:=]\s*)[^\s,&;\"']+"),
    re.compile(r"(?i)([?&](?:key|api_key|apikey|token|secret|password|subscription-key)=)[^&\s]+"),
    re.compile(
        r'(?i)("(?:authorization|x-api-key|subscription-key|[a-z0-9_ -]*api[_ -]?key|[a-z0-9_ -]*token|[a-z0-9_ -]*secret|[a-z0-9_ -]*password)"\s*:\s*")[^"]*(")'
    ),
    re.compile(
        r"(?i)('(?:authorization|x-api-key|subscription-key|[a-z0-9_ -]*api[_ -]?key|[a-z0-9_ -]*token|[a-z0-9_ -]*secret|[a-z0-9_ -]*password)'\s*:\s*')[^']*(')"
    ),
)


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = value
    for pattern in _TEXT_PATTERNS:
        redacted = pattern.sub(_replace_sensitive_match, redacted)
    return redacted


def redact_exception(exc: BaseException) -> str:
    return redact_text(str(exc)) or ""


def redact_mapping(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive_key(str(key)) else redact_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, tuple):
        return tuple(redact_mapping(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_mapping(item) for item in value]
    return value


def _replace_sensitive_match(match: re.Match[str]) -> str:
    if len(match.groups()) >= 2 and match.group(match.lastindex or 1).endswith(("\"", "'")):
        return f"{match.group(1)}{REDACTED}{match.group(2)}"
    return f"{match.group(1)}{REDACTED}"


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    if normalized in _SENSITIVE_TOKEN_FIELDS or normalized.endswith("token"):
        return True
    return any(marker in normalized for marker in _SENSITIVE_FIELD_MARKERS)
