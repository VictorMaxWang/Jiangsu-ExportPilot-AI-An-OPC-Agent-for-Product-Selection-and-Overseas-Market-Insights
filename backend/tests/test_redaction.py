from __future__ import annotations

from app.utils.redaction import REDACTED, redact_exception, redact_mapping, redact_text


def test_redact_text_masks_headers_query_params_and_json_fields() -> None:
    raw = (
        "Authorization: Bearer secret-token-value "
        "https://example.test/search?keyword=decor&api_key=secret-api-key&country=US "
        '{"ETSY_SHARED_SECRET":"etsy-secret-value","title":"sample"} '
        "subscription-key=un-secret-value"
    )

    redacted = redact_text(raw)

    assert redacted is not None
    assert "secret-token-value" not in redacted
    assert "secret-api-key" not in redacted
    assert "etsy-secret-value" not in redacted
    assert "un-secret-value" not in redacted
    assert redacted.count(REDACTED) >= 4
    assert "keyword=decor" in redacted
    assert '"title":"sample"' in redacted


def test_redact_mapping_recursively_masks_sensitive_keys_and_text_values() -> None:
    raw = {
        "keyword": "home decor",
        "headers": {
            "Authorization": "Bearer nested-secret",
            "x-api-key": "header-secret",
        },
        "items": [
            {"url": "https://example.test/?token=query-secret&country=US"},
            {"total_tokens": 12},
        ],
    }

    redacted = redact_mapping(raw)

    assert redacted == {
        "keyword": "home decor",
        "headers": {
            "Authorization": REDACTED,
            "x-api-key": REDACTED,
        },
        "items": [
            {"url": f"https://example.test/?token={REDACTED}&country=US"},
            {"total_tokens": 12},
        ],
    }


def test_redact_exception_returns_sanitized_message() -> None:
    exc = RuntimeError("API Key: exception-secret")

    redacted = redact_exception(exc)

    assert "exception-secret" not in redacted
    assert REDACTED in redacted
