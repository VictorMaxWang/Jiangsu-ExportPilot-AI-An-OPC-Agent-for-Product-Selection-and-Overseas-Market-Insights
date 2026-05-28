from collections.abc import Generator
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.api.ai import get_bailian_client
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import Product, ProductKeyword
from app.services.ai import BailianChatCompletion

_ = _models


def test_generate_product_keywords_persists_result_once() -> None:
    class StubClient:
        async def chat(
            self,
            messages: list[dict[str, str]],
            *,
            temperature: float = 0.7,
            max_tokens: int = 1200,
            json_mode: bool = False,
        ) -> BailianChatCompletion:
            payload = json.loads(messages[-1]["content"])
            assert payload["product_name_cn"] == "宠物凉感垫"
            assert payload["target_country"] == "JP"
            assert payload["target_platforms"] == ["Rakuten"]
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

    with _client_with_session_and_ai(StubClient()) as (client, session_factory):
        product_id = _create_product(client)

        response = client.post(
            f"/api/products/{product_id}/generate-keywords",
            json={"target_country": "JP", "target_platforms": ["Rakuten"]},
        )
        repeat_response = client.post(
            f"/api/products/{product_id}/generate-keywords",
            json={"target_country": "JP", "target_platforms": ["Rakuten"]},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["product_name_en"] == "Cooling Pet Mat"
        assert payload["keywords_en"] == ["pet cooling mat"]
        assert payload["keywords_jp"] == ["ペット 冷感 マット"]
        assert payload["target_users"] == ["pet owners"]
        assert payload["selling_points"] == ["cool touch fabric"]
        assert payload["risk_notes"] == ["verify material claims"]
        assert payload["saved_keywords_count"] == 2
        assert repeat_response.status_code == 200
        assert repeat_response.json()["saved_keywords_count"] == 0

        with session_factory() as db:
            product = db.get(Product, product_id)
            assert product is not None
            assert product.product_name_en == "Cooling Pet Mat"
            keyword_count = db.scalar(select(func.count()).select_from(ProductKeyword))
            assert keyword_count == 2


def test_generate_product_keywords_missing_product_does_not_call_ai() -> None:
    class StubClient:
        called = False

        async def chat(self, *args, **kwargs) -> BailianChatCompletion:  # noqa: ANN002, ANN003
            self.called = True
            return BailianChatCompletion(content="{}", model="qwen3.6-plus")

    stub = StubClient()
    with _client_with_session_and_ai(stub) as (client, _session_factory):
        response = client.post("/api/products/404/generate-keywords", json={})

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}
    assert not stub.called


def test_generate_product_keywords_missing_key_returns_503(monkeypatch) -> None:  # noqa: ANN001
    _clear_bailian_env(monkeypatch)
    get_settings.cache_clear()
    with _client_with_session_and_ai(None) as (client, _session_factory):
        product_id = _create_product(client)
        response = client.post(f"/api/products/{product_id}/generate-keywords", json={})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BAILIAN_NOT_CONFIGURED"
    response_text = response.text.lower()
    assert "authorization" not in response_text
    assert "bearer" not in response_text
    get_settings.cache_clear()


def test_generate_product_keywords_bad_json_returns_502() -> None:
    class BadJsonClient:
        async def chat(self, *args, **kwargs) -> BailianChatCompletion:  # noqa: ANN002, ANN003
            return BailianChatCompletion(content="not json", model="qwen3.6-plus")

    with _client_with_session_and_ai(BadJsonClient()) as (client, _session_factory):
        product_id = _create_product(client)
        response = client.post(f"/api/products/{product_id}/generate-keywords", json={})

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "AI_RESPONSE_PARSE_ERROR"


class _client_with_session_and_ai:
    def __init__(self, ai_client: object | None) -> None:
        self.ai_client = ai_client
        self.engine = None
        self.session_factory: sessionmaker[Session] | None = None

    def __enter__(self) -> tuple[TestClient, sessionmaker[Session]]:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        def override_get_db() -> Generator[Session, None, None]:
            assert self.session_factory is not None
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        if self.ai_client is not None:
            app.dependency_overrides[get_bailian_client] = lambda: self.ai_client
        self.client = TestClient(app)
        self.client.__enter__()
        return self.client, self.session_factory

    def __exit__(self, *args: object) -> None:
        self.client.__exit__(*args)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_bailian_client, None)
        Base.metadata.drop_all(bind=self.engine)


def _create_product(client: TestClient) -> int:
    company_response = client.post("/api/companies", json={"name": "Keyword Demo"})
    assert company_response.status_code == 201
    product_response = client.post(
        "/api/products",
        json={
            "company_id": company_response.json()["id"],
            "product_name_cn": "宠物凉感垫",
            "category": "Pet Home",
            "material": "Cooling fabric",
            "description": "夏季宠物用品",
        },
    )
    assert product_response.status_code == 201
    return int(product_response.json()["id"])


def _clear_bailian_env(monkeypatch) -> None:  # noqa: ANN001
    for name in (
        "DASHSCOPE_API_KEY",
        "BAILIAN_API_KEY",
        "SUPIN_DASHSCOPE_API_KEY",
        "SUPIN_BAILIAN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
