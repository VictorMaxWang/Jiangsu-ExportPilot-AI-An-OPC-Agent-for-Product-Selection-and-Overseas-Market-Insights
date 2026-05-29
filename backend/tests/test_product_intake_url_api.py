from __future__ import annotations

import asyncio
import json
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import DomesticProductLink, ProductDraft, ProductImportJob
from app.services.ai import BailianChatCompletion
from app.services.product_intake.domestic_page_fetcher import (
    DomesticPageFetchInput,
    DomesticPageFetchResult,
    fetch_domestic_product_page,
)


SUCCESS_PAYLOAD: dict[str, object] = {
    "source_platform": "jd",
    "product_name_cn": "宠物凉感垫",
    "product_name_en": "Pet Cooling Mat",
    "category": "Pet supplies",
    "price_cny": 39.9,
    "material": "尼龙",
    "specification": "夏季宠物垫",
    "dimensions": None,
    "weight_estimate": None,
    "color_options": ["蓝色"],
    "selling_points_cn": ["夏季降温"],
    "selling_points_en": ["Cooling mat for summer"],
    "target_users": ["pet owners"],
    "usage_scenarios": ["home"],
    "cross_border_keywords_en": ["pet cooling mat"],
    "risk_notes": ["URL text is public page text and requires manual review."],
    "confidence_score": 0.82,
    "evidence": [{"field": "product_name_cn", "source": "url_text", "value": "宠物凉感垫"}],
}


@pytest.fixture()
def client_with_session() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, testing_session_local
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_bailian_client, None)
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)


def test_page_fetcher_login_or_risk_page_returns_needs_screenshot() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><title>安全验证</title><body>请先登录，完成验证码安全验证</body></html>",
        )

    result = asyncio.run(
        fetch_domestic_product_page(
            DomesticPageFetchInput(
                platform="jd",
                original_url="https://item.jd.com/100012043978.html",
                normalized_url="https://item.jd.com/100012043978.html",
                item_id="100012043978",
                sku_id="100012043978",
            ),
            transport=httpx.MockTransport(handler),
            resolver=_public_resolver,
        )
    )

    assert result.parse_status == "needs_screenshot"
    assert result.error_code == "URL_PARSE_BLOCKED"
    assert result.message == "请上传截图继续分析"
    serialized = json.dumps(result.__dict__, ensure_ascii=False)
    assert "<html" not in serialized.lower()
    assert "请先登录" not in serialized


@pytest.mark.parametrize("status_code", [403, 429, 500])
def test_page_fetcher_http_failures_return_needs_screenshot(status_code: int) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"content-type": "text/html"}, text="<html>blocked</html>")

    result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(handler),
            resolver=_public_resolver,
        )
    )

    assert result.parse_status == "needs_screenshot"
    assert result.message == "请上传截图继续分析"


def test_page_fetcher_timeout_non_html_and_oversized_return_needs_screenshot() -> None:
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async def json_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    async def oversized_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 32)

    timeout_result = asyncio.run(
        fetch_domestic_product_page(_fetch_input(), transport=httpx.MockTransport(timeout_handler), resolver=_public_resolver)
    )
    json_result = asyncio.run(
        fetch_domestic_product_page(_fetch_input(), transport=httpx.MockTransport(json_handler), resolver=_public_resolver)
    )
    oversized_result = asyncio.run(
        fetch_domestic_product_page(
            _fetch_input(),
            transport=httpx.MockTransport(oversized_handler),
            resolver=_public_resolver,
            max_response_bytes=8,
        )
    )

    assert timeout_result.parse_status == "needs_screenshot"
    assert timeout_result.error_code == "URL_FETCH_TIMEOUT"
    assert json_result.parse_status == "needs_screenshot"
    assert json_result.error_code == "URL_CONTENT_TYPE_UNSUPPORTED"
    assert oversized_result.parse_status == "needs_screenshot"
    assert oversized_result.error_code == "URL_RESPONSE_TOO_LARGE"


def test_url_intake_qwen_mock_success_creates_job_link_and_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_with_session
    _configure_url_env(monkeypatch)
    fake_ai = FakeTextClient(json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False))
    fake_fetch = FakePageFetcher(_parsed_fetch_result())
    app.dependency_overrides[get_bailian_client] = lambda: fake_ai
    monkeypatch.setattr("app.services.product_intake.url_intake.fetch_domestic_product_page", fake_fetch)
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/url",
        json={"company_id": company_id, "url": "https://item.jd.com/100012043978.html?token=secret-token"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "draft_ready"
    assert payload["message"] == "draft_ready"
    assert payload["draft"]["product_name_cn"] == "宠物凉感垫"
    assert fake_fetch.calls == ["https://item.jd.com/100012043978.html"]
    assert len(fake_ai.calls) == 1
    ai_call_text = json.dumps(fake_ai.calls, ensure_ascii=False)
    assert "secret-token" not in ai_call_text
    assert "Authorization" not in ai_call_text
    assert "Cookie" not in ai_call_text
    assert "<html" not in ai_call_text
    assert "fake-secret-key" not in response.text
    assert "secret-token" not in response.text

    with session_factory() as db:
        job = db.get(ProductImportJob, payload["job_id"])
        link = db.scalar(select(DomesticProductLink).where(DomesticProductLink.import_job_id == payload["job_id"]))
        draft = db.get(ProductDraft, payload["draft_id"])
        assert job is not None and job.source_type == "url"
        assert job.status == "draft_ready"
        assert job.source_platform == "jd"
        assert link is not None and link.platform == "jd"
        assert link.sku_id == "100012043978"
        assert link.parse_status == "parsed"
        assert link.parsed_text is not None and "宠物凉感垫" in link.parsed_text
        assert draft is not None and draft.source_platform == "jd"
        assert draft.price_cny is not None
        assert draft.evidence and draft.evidence[0]["source"] == "url_text"


def test_url_intake_fetch_failure_falls_back_to_needs_screenshot(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_with_session
    _configure_url_env(monkeypatch)
    fake_ai = FakeTextClient(json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False))
    fake_fetch = FakePageFetcher(
        DomesticPageFetchResult(parse_status="needs_screenshot", error_code="URL_FETCH_TIMEOUT", message="请上传截图继续分析")
    )
    app.dependency_overrides[get_bailian_client] = lambda: fake_ai
    monkeypatch.setattr("app.services.product_intake.url_intake.fetch_domestic_product_page", fake_fetch)
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/url",
        json={"company_id": company_id, "url": "https://item.jd.com/100012043978.html"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "needs_screenshot"
    assert payload["message"] == "请上传截图继续分析"
    assert payload["draft"]["product_name_cn"] is None
    assert fake_ai.calls == []
    assert "URL_FETCH_TIMEOUT" not in response.text

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 1
        link = db.scalar(select(DomesticProductLink))
        draft = db.get(ProductDraft, payload["draft_id"])
        assert link is not None and link.parse_status == "needs_screenshot"
        assert draft is not None and draft.product_name_cn is None
        assert draft.confidence_score == 0


def test_url_intake_rejects_unsafe_url_before_db_write(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = client_with_session
    _configure_url_env(monkeypatch)
    fake_ai = FakeTextClient(json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False))
    fake_fetch = FakePageFetcher(_parsed_fetch_result())
    app.dependency_overrides[get_bailian_client] = lambda: fake_ai
    monkeypatch.setattr("app.services.product_intake.url_intake.fetch_domestic_product_page", fake_fetch)
    company_id = _create_company(client)

    response = client.post("/api/product-intake/url", json={"company_id": company_id, "url": "http://localhost/item"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "URL_SECURITY_BLOCKED"
    assert fake_ai.calls == []
    assert fake_fetch.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


class FakeTextClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1800,
        json_mode: bool = True,
    ) -> BailianChatCompletion:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_mode": json_mode,
            }
        )
        return BailianChatCompletion(content=self.content, model="qwen3.6-plus")


class FakePageFetcher:
    def __init__(self, result: DomesticPageFetchResult) -> None:
        self.result = result
        self.calls: list[str] = []

    async def __call__(self, parsed: DomesticPageFetchInput) -> DomesticPageFetchResult:
        self.calls.append(parsed.normalized_url)
        return self.result


def _configure_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_DOMESTIC_URL_FETCH", "true")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-key")
    get_settings.cache_clear()


def _create_company(client: TestClient) -> int:
    response = client.post(
        "/api/companies",
        json={
            "name": "Nantong Demo Home Textile",
            "region": "Nantong",
            "industry": "Home textiles",
            "description": "Product intake test company",
            "target_countries": ["US", "JP"],
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _public_resolver(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


def _fetch_input() -> DomesticPageFetchInput:
    return DomesticPageFetchInput(
        platform="jd",
        original_url="https://item.jd.com/100012043978.html",
        normalized_url="https://item.jd.com/100012043978.html",
        item_id="100012043978",
        sku_id="100012043978",
    )


def _parsed_fetch_result() -> DomesticPageFetchResult:
    return DomesticPageFetchResult(
        parse_status="parsed",
        title="宠物凉感垫 - 京东",
        meta_description="夏季宠物凉感垫，参考价￥39.90",
        og_title="宠物凉感垫",
        og_image="https://img.example.com/product.jpg",
        visible_text="宠物凉感垫 夏季降温 尼龙材质 参考价￥39.90",
        price_candidates=["参考价￥39.90"],
        product_name_candidates=["宠物凉感垫"],
        http_status=200,
        final_url="https://item.jd.com/100012043978.html",
        message="parsed",
    )
