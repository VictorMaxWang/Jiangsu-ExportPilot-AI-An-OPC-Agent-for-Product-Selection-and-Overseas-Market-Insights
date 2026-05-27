from __future__ import annotations

import json
import re
from typing import Any


class AiJsonParseError(ValueError):
    pass


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise AiJsonParseError("AI response content was empty.")

    parsed = _loads_object(text)
    if parsed is not None:
        return parsed

    fenced = _strip_json_fence(text)
    if fenced != text:
        parsed = _loads_object(fenced)
        if parsed is not None:
            return parsed

    extracted = _extract_first_json_object(text)
    if extracted is not None:
        parsed = _loads_object(extracted)
        if parsed is not None:
            return parsed

    raise AiJsonParseError("AI response was not a valid JSON object.")


def _loads_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        raise AiJsonParseError("AI response JSON was not an object.")
    return value


def _strip_json_fence(text: str) -> str:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return text
    return match.group(1).strip()


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
