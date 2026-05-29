import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.ai import get_bailian_client
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas import ProductKeywordsResponse
from app.services.ai import (
    BailianChatCompletion,
    BailianClient,
    BailianTimeoutError,
    BailianUpstreamError,
    BailianVisionDisabledError,
)
from app.services.ai.json_parser import AiJsonParseError, parse_json_object


def test_bailian_settings_defaults_and_key_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_bailian_env(monkeypatch)
    get_settings.cache_clear()
    defaults = get_settings()
    assert defaults.bailian_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert defaults.bailian_model == "qwen3.6-plus"
    assert defaults.bailian_api_key is None

    monkeypatch.setenv("BAILIAN_API_KEY", "bailian-fake-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-fake-key")
    get_settings.cache_clear()
    assert get_settings().bailian_api_key == "dashscope-fake-key"

    monkeypatch.delenv("DASHSCOPE_API_KEY")
    get_settings.cache_clear()
    assert get_settings().bailian_api_key == "bailian-fake-key"
    get_settings.cache_clear()


def test_bailian_client_success_and_json_mode_request() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content.decode())
        assert payload["model"] == "qwen3.6-plus"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "model": "qwen3.6-plus",
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
                "usage": {"total_tokens": 12},
            },
        )

    client = BailianClient(
        Settings(
            bailian_api_key="client-fake-key",
            bailian_base_url="https://example.test/compatible-mode/v1",
            bailian_max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.chat([{"role": "user", "content": "hello"}], json_mode=True))

    assert result.content == "{\"ok\": true}"
    assert result.model == "qwen3.6-plus"
    assert result.usage == {"total_tokens": 12}
    assert requests[0].url.path == "/compatible-mode/v1/chat/completions"


def test_bailian_vision_chat_disabled_does_not_send_request() -> None:
    called = False

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    client = BailianClient(
        Settings(
            bailian_api_key="vision-disabled-fake-key",
            bailian_vision_enabled=False,
            bailian_vision_model="qwen-vl-test",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BailianVisionDisabledError):
        asyncio.run(client.vision_chat([{"role": "user", "content": "hello"}]))

    assert called is False


def test_bailian_vision_chat_uses_configured_model_and_image_payload() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content.decode())
        assert payload["model"] == "qwen-vl-from-env"
        assert payload["response_format"] == {"type": "json_object"}
        content = payload["messages"][1]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            json={
                "model": "qwen-vl-from-env",
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
                "usage": {"total_tokens": 20},
            },
        )

    client = BailianClient(
        Settings(
            bailian_api_key="vision-fake-key",
            bailian_base_url="https://example.test/compatible-mode/v1",
            bailian_vision_enabled=True,
            bailian_vision_model="qwen-vl-from-env",
            bailian_max_retries=0,
        ),
        transport=httpx.MockTransport(handler),
    )
    messages = [
        {"role": "system", "content": "Return JSON."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze screenshot."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
    ]

    result = asyncio.run(client.vision_chat(messages, json_mode=True))

    assert result.content == "{\"ok\": true}"
    assert result.model == "qwen-vl-from-env"
    assert result.usage == {"total_tokens": 20}
    assert requests[0].url.path == "/compatible-mode/v1/chat/completions"


def test_bailian_client_retries_transient_status() -> None:
    call_count = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = BailianClient(
        Settings(bailian_api_key="retry-fake-key", bailian_max_retries=1),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.chat([{"role": "user", "content": "hello"}]))

    assert result.content == "ok"
    assert call_count == 2


def test_bailian_client_does_not_retry_bad_request() -> None:
    call_count = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(400, json={"error": "bad request"})

    client = BailianClient(
        Settings(bailian_api_key="bad-request-fake-key", bailian_max_retries=2),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BailianUpstreamError):
        asyncio.run(client.chat([{"role": "user", "content": "hello"}]))
    assert call_count == 1


def test_bailian_client_timeout_maps_to_sanitized_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("request timed out", request=request)

    client = BailianClient(
        Settings(bailian_api_key="timeout-fake-key", bailian_max_retries=0),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BailianTimeoutError):
        asyncio.run(client.chat([{"role": "user", "content": "hello"}]))


def test_parse_json_object_accepts_common_model_wrappers() -> None:
    assert parse_json_object('{"ok": true}') == {"ok": True}
    assert parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}
    assert parse_json_object('Here is the JSON: {"ok": true}') == {"ok": True}


@pytest.mark.parametrize("content", ["", "not json", "[1, 2, 3]"])
def test_parse_json_object_rejects_invalid_content(content: str) -> None:
    with pytest.raises(AiJsonParseError):
        parse_json_object(content)


def test_product_keywords_schema_rejects_missing_or_invalid_fields() -> None:
    with pytest.raises(ValidationError):
        ProductKeywordsResponse.model_validate({"product_name_en": "Cooling Pet Mat"})

    with pytest.raises(ValidationError):
        ProductKeywordsResponse.model_validate(
            {
                "product_name_en": "Cooling Pet Mat",
                "keywords_en": "pet cooling mat",
                "keywords_jp": [],
                "target_users": [],
                "selling_points": [],
                "risk_notes": [],
            }
        )


def test_ai_api_missing_key_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_bailian_env(monkeypatch)
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hello"}]})

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "BAILIAN_NOT_CONFIGURED"
    response_text = response.text.lower()
    assert "authorization" not in response_text
    assert "bearer" not in response_text
    get_settings.cache_clear()


def test_ai_api_endpoints_return_structured_payloads() -> None:
    class StubClient:
        async def chat(
            self,
            messages: list[dict[str, str]],
            *,
            temperature: float = 0.7,
            max_tokens: int = 1200,
            json_mode: bool = False,
        ) -> BailianChatCompletion:
            if not json_mode:
                return BailianChatCompletion(content="plain response", model="qwen3.6-plus", usage=None)
            user_payload = json.loads(messages[-1]["content"])
            if "product_name_cn" in user_payload:
                return BailianChatCompletion(
                    content=json.dumps(
                        {
                            "product_name_en": "Cooling Pet Mat",
                            "keywords_en": ["pet cooling mat"],
                            "keywords_jp": ["ペット 冷感 マット"],
                            "target_users": ["pet owners"],
                            "selling_points": ["cool touch fabric"],
                            "risk_notes": ["verify material claims"],
                        },
                        ensure_ascii=False,
                    ),
                    model="qwen3.6-plus",
                )
            if "target_language" in user_payload:
                return BailianChatCompletion(
                    content=json.dumps(
                        {
                            "listing_title": "Cooling Pet Mat",
                            "short_description": "A cool-touch mat for warm days.",
                            "bullet_points": ["Easy to fold"],
                            "ad_copy": "Help pets rest more comfortably in summer.",
                            "social_posts": ["Summer comfort for pets."],
                            "seo_keywords": ["pet mat"],
                            "localization_notes": ["Avoid unverified cooling claims."],
                        }
                    ),
                    model="qwen3.6-plus",
                )
            return BailianChatCompletion(
                content=json.dumps(
                    {
                        "section_title": "Market Overview",
                        "content_markdown": "## Market Overview\nEvidence is limited.",
                    }
                ),
                model="qwen3.6-plus",
            )

    with _override_ai_client(StubClient()):
        with TestClient(app) as client:
            chat_response = client.post(
                "/api/ai/chat",
                json={"messages": [{"role": "user", "content": "hello"}]},
            )
            keywords_response = client.post(
                "/api/ai/product-keywords",
                json={"product_name_cn": "宠物凉感垫", "description": "夏季宠物用品"},
            )
            copy_response = client.post(
                "/api/ai/marketing-copy",
                json={
                    "product_name": "Cooling Pet Mat",
                    "target_country": "US",
                    "target_language": "en",
                },
            )
            report_response = client.post(
                "/api/ai/report-section",
                json={"section_type": "overview", "product_name": "Cooling Pet Mat"},
            )

    assert chat_response.status_code == 200
    assert chat_response.json()["content"] == "plain response"
    assert keywords_response.status_code == 200
    assert keywords_response.json() == {
        "product_name_en": "Cooling Pet Mat",
        "keywords_en": ["pet cooling mat"],
        "keywords_jp": ["ペット 冷感 マット"],
        "target_users": ["pet owners"],
        "selling_points": ["cool touch fabric"],
        "risk_notes": ["verify material claims"],
    }
    assert copy_response.status_code == 200
    assert copy_response.json()["listing_title"] == "Cooling Pet Mat"
    assert report_response.status_code == 200
    assert report_response.json()["section_title"] == "Market Overview"


def test_product_keywords_bad_json_returns_502() -> None:
    class BadJsonClient:
        async def chat(self, *args, **kwargs) -> BailianChatCompletion:  # noqa: ANN002, ANN003
            return BailianChatCompletion(content="not json", model="qwen3.6-plus")

    with _override_ai_client(BadJsonClient()):
        with TestClient(app) as client:
            response = client.post(
                "/api/ai/product-keywords",
                json={"product_name_cn": "宠物凉感垫"},
            )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AI_RESPONSE_PARSE_ERROR"


class _override_ai_client:
    def __init__(self, client: object) -> None:
        self.client = client

    def __enter__(self) -> None:
        app.dependency_overrides[get_bailian_client] = lambda: self.client

    def __exit__(self, *args: object) -> None:
        app.dependency_overrides.pop(get_bailian_client, None)


def _clear_bailian_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DASHSCOPE_API_KEY",
        "BAILIAN_API_KEY",
        "SUPIN_DASHSCOPE_API_KEY",
        "SUPIN_BAILIAN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
