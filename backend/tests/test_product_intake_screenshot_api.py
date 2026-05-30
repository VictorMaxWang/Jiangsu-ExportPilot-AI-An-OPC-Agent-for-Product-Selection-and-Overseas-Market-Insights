from __future__ import annotations

import json
from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import ProductDraft, ProductImportAsset, ProductImportJob
from app.services.ai import BailianChatCompletion, BailianTimeoutError


SUCCESS_PAYLOAD: dict[str, object] = {
    "source_platform": "taobao",
    "product_name_cn": "宠物凉感垫",
    "product_name_en": "Pet Cooling Mat",
    "category": "Pet supplies",
    "price_cny": 39.9,
    "material": None,
    "specification": "Visible foldable mat product page",
    "dimensions": None,
    "weight_estimate": None,
    "color_options": ["蓝色"],
    "selling_points_cn": ["夏季宠物用品"],
    "selling_points_en": ["Summer pet accessory"],
    "target_users": ["pet owners"],
    "usage_scenarios": ["home cooling"],
    "cross_border_keywords_en": ["pet cooling mat"],
    "risk_notes": ["Material and size require manual confirmation."],
    "confidence_score": 0.82,
    "evidence": [
        {
            "field": "product_name_cn",
            "source": "screenshot_text",
            "value": "宠物凉感垫",
        }
    ],
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


def test_non_image_mime_is_rejected_without_ai_call(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("note.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_TYPE"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


def test_oversized_image_is_rejected_without_ai_call(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path, max_mb=0.0001)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("large.png", b"x" * 512, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "IMAGE_TOO_LARGE"
    assert fake.calls == []
    assert not (tmp_path / "uploads").exists()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


def test_damaged_image_content_is_rejected_without_ai_call(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("broken.png", b"not really a png", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_CONTENT"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


@pytest.mark.parametrize(
    ("image_format", "mime_type", "expected_extension"),
    [("JPEG", "image/jpeg", ".jpg"), ("WEBP", "image/webp", ".webp")],
)
def test_screenshot_upload_accepts_jpeg_and_webp(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    image_format: str,
    mime_type: str,
    expected_extension: str,
) -> None:
    client, _session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id), "source_platform": "jd"},
        files={"file": (f"product{expected_extension}", _image_bytes(image_format), mime_type)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["asset"]["mime_type"] == mime_type
    assert payload["asset"]["file_name"].endswith(expected_extension)
    assert payload["draft"]["product_name_cn"] == "宠物凉感垫"
    assert len(fake.calls) == 1


def test_screenshot_upload_rejects_mime_content_mismatch_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("mismatch.png", _image_bytes("JPEG"), "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_CONTENT"
    assert fake.calls == []
    assert not (tmp_path / "uploads").exists()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


def test_empty_screenshot_file_is_rejected_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("empty.png", b"", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_CONTENT"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


@pytest.mark.parametrize(
    ("enabled", "model", "expected_code"),
    [
        ("false", "qwen-vl-test", "BAILIAN_VISION_DISABLED"),
        ("true", "", "BAILIAN_VISION_MODEL_NOT_CONFIGURED"),
    ],
)
def test_vision_disabled_or_missing_model_creates_manual_draft_without_ai_call(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    enabled: str,
    model: str,
    expected_code: str,
) -> None:
    client, _session_factory = client_with_session
    monkeypatch.setenv("PRODUCT_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_PRODUCT_IMAGE_SIZE_MB", "10")
    monkeypatch.setenv("BAILIAN_VISION_ENABLED", enabled)
    monkeypatch.setenv("BAILIAN_VISION_MODEL", model)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-key")
    get_settings.cache_clear()
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["error_code"] == expected_code
    assert payload["next_action"] == "manual_fill"
    assert payload["ai_result_type"] == "fallback"
    assert payload["ai_fallback_used"] is True
    assert payload["model_used"] is None
    assert payload["draft"]["product_name_cn"] is None
    assert fake.calls == []


def test_screenshot_company_not_found_rejected_before_file_write(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": "99999"},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "COMPANY_NOT_FOUND"
    assert fake.calls == []
    assert not (tmp_path / "uploads").exists()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductImportJob)) == 0


def test_screenshot_upload_creates_job_asset_and_draft_with_safe_filename(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id), "source_platform": "taobao"},
        files={"file": ("../../secret-product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready"
    assert payload["low_confidence"] is False
    assert payload["error_code"] is None
    assert payload["ai_result_type"] == "real_qwen"
    assert payload["ai_fallback_used"] is False
    assert payload["model_used"] == "qwen-vl-test"
    assert payload["asset"]["mime_type"] == "image/png"
    assert payload["draft"]["product_name_cn"] == "宠物凉感垫"
    assert fake.calls and fake.calls[0]["json_mode"] is True
    response_text = response.text
    assert "secret-product.png" not in response_text
    assert "file_path" not in response_text
    assert "Authorization" not in response_text
    assert "Bearer" not in response_text
    assert "fake-secret-key" not in response_text

    upload_dir = tmp_path / "uploads"
    stored_files = list(upload_dir.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name == payload["asset"]["file_name"]
    assert ".." not in payload["asset"]["file_name"]
    assert "secret" not in payload["asset"]["file_name"]

    with session_factory() as db:
        job = db.get(ProductImportJob, payload["import_job_id"])
        asset = db.get(ProductImportAsset, payload["asset"]["id"])
        draft = db.get(ProductDraft, payload["draft_id"])
        assert job is not None and job.status == "draft_ready"
        assert asset is not None and asset.file_name == payload["asset"]["file_name"]
        assert draft is not None and draft.product_name_cn == "宠物凉感垫"
        assert draft.price_cny is not None
        assert draft.cost_price_cny is None


def test_screenshot_ai_sensitive_evidence_is_redacted_in_response_and_db(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    sensitive_payload = {
        **_success_payload(),
        "evidence": [
            {
                "field": "product_name_cn",
                "source": "screenshot_text",
                "value": "宠物凉感垫 联系 13812345678 user@example.com C:\\Users\\demo\\secret.png 123456789012",
            }
        ],
    }
    fake = FakeVisionClient(json.dumps(sensitive_payload, ensure_ascii=False))
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    draft_response = client.get(f"/api/product-intake/drafts/{response.json()['draft_id']}")
    assert draft_response.status_code == 200
    response_text = response.text + draft_response.text
    assert "13812345678" not in response_text
    assert "user@example.com" not in response_text
    assert "C:\\Users\\demo\\secret.png" not in response_text
    assert "123456789012" not in response_text
    assert "[REDACTED_PHONE]" in response_text
    assert "[REDACTED_EMAIL]" in response_text
    with session_factory() as db:
        draft = db.get(ProductDraft, response.json()["draft_id"])
        assert draft is not None
        evidence_text = json.dumps(draft.evidence, ensure_ascii=False)
        assert "13812345678" not in evidence_text
        assert "user@example.com" not in evidence_text
        assert "C:\\Users\\demo\\secret.png" not in evidence_text
        assert "123456789012" not in evidence_text


def test_ai_timeout_returns_low_confidence_manual_draft_without_secret_leak(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(exc=BailianTimeoutError("Authorization: Bearer sentinel-secret"))
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["low_confidence"] is True
    assert payload["error_code"] == "BAILIAN_TIMEOUT"
    assert payload["next_action"] == "manual_fill"
    assert payload["ai_result_type"] == "fallback"
    assert payload["ai_fallback_used"] is True
    assert payload["draft"]["product_name_cn"] is None
    assert "sentinel-secret" not in response.text
    assert "Authorization" not in response.text
    assert "Bearer" not in response.text
    with session_factory() as db:
        draft = db.get(ProductDraft, payload["draft_id"])
        assert draft is not None
        assert draft.product_name_cn is None
        assert draft.confidence_score == 0


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        ("not json", "AI_RESPONSE_PARSE_ERROR"),
        (json.dumps({"product_name_cn": "宠物凉感垫"}), "AI_RESPONSE_SCHEMA_ERROR"),
        (
            json.dumps(
                {
                    **SUCCESS_PAYLOAD,
                    "product_name_cn": "",
                    "confidence_score": 0.9,
                },
                ensure_ascii=False,
            ),
            "AI_PRODUCT_NOT_IDENTIFIED",
        ),
    ],
)
def test_ai_invalid_or_unidentified_output_returns_manual_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    content: str,
    expected_code: str,
) -> None:
    client, _session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(content)
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["error_code"] == expected_code
    assert payload["low_confidence"] is True
    assert payload["draft"]["product_name_cn"] is None
    if expected_code in {"AI_RESPONSE_PARSE_ERROR", "AI_RESPONSE_SCHEMA_ERROR"}:
        assert payload["ai_result_type"] == "fallback"
        assert payload["ai_fallback_used"] is True
    else:
        assert payload["ai_result_type"] == "manual_required"
        assert payload["ai_fallback_used"] is False


def test_low_confidence_ai_output_creates_reviewable_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(json.dumps({**_success_payload(), "confidence_score": 0.4}, ensure_ascii=False))
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)

    response = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("product.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["error_code"] == "LOW_CONFIDENCE"
    assert payload["low_confidence"] is True
    assert payload["next_action"] == "manual_review"
    assert payload["ai_result_type"] == "manual_required"
    assert payload["ai_fallback_used"] is False
    assert payload["model_used"] == "qwen-vl-test"
    assert payload["draft"]["product_name_cn"] == "宠物凉感垫"


def test_get_job_and_draft_responses_do_not_expose_internal_file_details(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    company_id = _create_company(client)
    created = client.post(
        "/api/product-intake/screenshot",
        data={"company_id": str(company_id)},
        files={"file": ("catalog-secret.png", _image_bytes("PNG"), "image/png")},
    ).json()

    job_response = client.get(f"/api/product-intake/jobs/{created['import_job_id']}")
    draft_response = client.get(f"/api/product-intake/drafts/{created['draft_id']}")

    assert job_response.status_code == 200
    assert draft_response.status_code == 200
    combined = job_response.text + draft_response.text
    assert "file_path" not in combined
    assert "raw_text" not in combined
    assert "base64" not in combined
    assert "catalog-secret.png" not in combined
    assert str(tmp_path) not in combined
    assert "Authorization" not in combined
    assert "Bearer" not in combined
    assert "Cookie" not in combined


class FakeVisionClient:
    def __init__(self, content: str | None = None, *, exc: Exception | None = None) -> None:
        self.content = content or _success_json()
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    async def vision_chat(
        self,
        messages: list[dict[str, object]],
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
        if self.exc is not None:
            raise self.exc
        return BailianChatCompletion(content=self.content, model="qwen-vl-test")


def _configure_intake_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    max_mb: float = 10.0,
) -> None:
    monkeypatch.setenv("PRODUCT_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MAX_PRODUCT_IMAGE_SIZE_MB", str(max_mb))
    monkeypatch.setenv("BAILIAN_VISION_ENABLED", "true")
    monkeypatch.setenv("BAILIAN_VISION_MODEL", "qwen-vl-test")
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


def _image_bytes(image_format: str) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (8, 6), color=(120, 180, 220))
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _success_json() -> str:
    return json.dumps(_success_payload(), ensure_ascii=False)


def _success_payload() -> dict[str, object]:
    return dict(SUCCESS_PAYLOAD)
