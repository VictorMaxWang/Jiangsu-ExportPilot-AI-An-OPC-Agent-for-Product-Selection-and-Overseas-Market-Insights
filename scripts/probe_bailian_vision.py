from __future__ import annotations

import base64
import json
import os
import re
import struct
import zlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
NATIVE_PATH = "/api/v1/services/aigc/multimodal-generation/generation"
SAFE_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


def main() -> None:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    model = _blank_to_none(os.getenv("BAILIAN_VISION_MODEL"))
    base_url = _blank_to_none(os.getenv("BAILIAN_BASE_URL")) or DEFAULT_BASE_URL

    if not api_key:
        print(json.dumps([_result(model, "configuration", False, None, "DASHSCOPE_API_KEY_NOT_CONFIGURED")]))
        return
    if not model:
        print(json.dumps([_result(model, "configuration", False, None, "BAILIAN_VISION_MODEL_NOT_CONFIGURED")]))
        return

    data_url = _small_png_data_url()
    timeout = httpx.Timeout(30.0, connect=5.0, read=30.0, write=10.0, pool=5.0)
    results: list[dict[str, object]] = []

    with httpx.Client(timeout=timeout) as client:
        openai_result = _probe_openai_compatible(client, base_url, api_key, model, data_url)
        results.append(openai_result)
        if not openai_result["success"]:
            results.append(_probe_dashscope_native(client, base_url, api_key, model, data_url))

    print(json.dumps(results, ensure_ascii=False, separators=(",", ":")))


def _probe_openai_compatible(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    data_url: str,
) -> dict[str, object]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only JSON. Do not include secrets."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": 'Inspect this smoke image and return exactly {"ok": true, "image_seen": true}.',
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0,
        "max_tokens": 48,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    return _post_probe(
        client,
        endpoint,
        api_key,
        payload,
        model=model,
        method="openai_compatible_image_url",
    )


def _probe_dashscope_native(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    data_url: str,
) -> dict[str, object]:
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": data_url},
                        {"text": 'Inspect this smoke image and return exactly {"ok": true, "image_seen": true}.'},
                    ],
                }
            ]
        },
    }
    return _post_probe(
        client,
        _dashscope_native_endpoint(base_url),
        api_key,
        payload,
        model=model,
        method="dashscope_native_multimodal",
    )


def _post_probe(
    client: httpx.Client,
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    model: str,
    method: str,
) -> dict[str, object]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = client.post(endpoint, headers=headers, json=payload)
    except httpx.TimeoutException:
        return _result(model, method, False, None, "REQUEST_TIMEOUT")
    except httpx.HTTPError:
        return _result(model, method, False, None, "REQUEST_FAILED")

    sanitized_error = _safe_response_error_code(response)
    if response.status_code >= 400:
        return _result(model, method, False, response.status_code, sanitized_error or f"HTTP_{response.status_code}")

    if not _response_confirms_image_seen(response, method):
        return _result(model, method, False, response.status_code, "VISION_SMOKE_RESPONSE_INVALID")

    return _result(model, method, True, response.status_code, None)


def _response_confirms_image_seen(response: httpx.Response, method: str) -> bool:
    try:
        data = response.json()
    except ValueError:
        return False

    content: object | None = None
    if method == "openai_compatible_image_url":
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return False
    else:
        try:
            content = data["output"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return False

    text = _content_to_text(content)
    if not text:
        return False
    parsed = _parse_json_object(text)
    return parsed.get("ok") is True and parsed.get("image_seen") is True


def _content_to_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts) if parts else None
    return None


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_response_error_code(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    nested_error = data.get("error")
    candidates: list[object] = [data.get("code"), data.get("type"), data.get("status_name")]
    if isinstance(nested_error, dict):
        candidates.extend([nested_error.get("code"), nested_error.get("type")])

    for candidate in candidates:
        if isinstance(candidate, str):
            value = candidate.strip()
            if SAFE_CODE_RE.fullmatch(value):
                return value
    return None


def _result(
    model: str | None,
    method: str,
    success: bool,
    status_code: int | None,
    sanitized_error: str | None,
) -> dict[str, object]:
    return {
        "model": model,
        "method": method,
        "success": success,
        "status_code": status_code,
        "sanitized_error": sanitized_error,
        "suggested_action": _suggested_action(method, success, status_code, sanitized_error),
    }


def _suggested_action(
    method: str,
    success: bool,
    status_code: int | None,
    sanitized_error: str | None,
) -> str:
    normalized = (sanitized_error or "").casefold()
    if success and method == "openai_compatible_image_url":
        return "OpenAI-compatible image_url data URL is usable for the configured vision model."
    if success:
        return "DashScope native multimodal is usable; route vision calls through native multimodal if OpenAI-compatible remains unavailable."
    if sanitized_error == "DASHSCOPE_API_KEY_NOT_CONFIGURED":
        return "Set DASHSCOPE_API_KEY in the backend runtime environment before probing."
    if sanitized_error == "BAILIAN_VISION_MODEL_NOT_CONFIGURED":
        return "Set BAILIAN_VISION_MODEL to a vision model available to this Bailian/DashScope account."
    if status_code == 404 or "modelnotfound" in normalized or "model_not_found" in normalized:
        return "The configured BAILIAN_VISION_MODEL appears unavailable or misspelled for this account and region."
    if status_code in {401, 403} or "accessdenied" in normalized or "forbidden" in normalized:
        return "Confirm the DashScope account, workspace, and Bailian console authorization for this vision model."
    if "model_not_supported" in normalized or "notcompatible" in normalized:
        return "OpenAI-compatible may not support this model/method; prefer DashScope native multimodal if that probe succeeds."
    if status_code == 400:
        return "Check image size/format, BAILIAN_VISION_MODEL, and whether this model requires DashScope native multimodal."
    if status_code == 429:
        return "Retry later or reduce probe frequency; do not change the model automatically."
    return "Review backend Bailian vision configuration and rerun this probe once."


def _dashscope_native_endpoint(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if not parsed.scheme or not parsed.netloc:
        parsed = urlsplit(DEFAULT_BASE_URL)
    return urlunsplit((parsed.scheme, parsed.netloc, NATIVE_PATH, "", ""))


def _small_png_data_url() -> str:
    width = 32
    height = 32
    row = b"\x00" + b"\x28\x78\xc8" * width
    raw = row * height
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
    return f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


if __name__ == "__main__":
    main()
