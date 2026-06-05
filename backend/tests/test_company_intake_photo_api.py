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

from app import models as _models
from app.api.ai import get_bailian_client
from app.core.config import get_settings
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import Company, CompanyDraft, CompanyImportJob
from app.services.ai import BailianChatCompletion, BailianTimeoutError

_ = _models


SUCCESS_PAYLOAD: dict[str, object] = {
    "company_name": "Suzhou Export Pilot Co",
    "credit_code_suffix": "91320506MA1ABCDE12",
    "region": "Jiangsu Suzhou",
    "industry": "Home goods manufacturing",
    "description": "Visible brochure shows a Jiangsu home goods manufacturer.",
    "main_products": ["storage baskets", "home organizers"],
    "target_countries": ["US", "JP"],
    "website": "https://example.com/company?token=secret-token",
    "contact_role": "Export sales manager",
    "risk_notes": ["Company identity and products require manual confirmation."],
    "confidence_score": 0.82,
    "evidence": [
        {
            "field": "company_name",
            "source": "photo_text",
            "image_index": 0,
            "image_role": "business_license",
            "value": "Suzhou Export Pilot Co",
        },
        {
            "field": "main_products",
            "source": "photo_visual",
            "image_index": 1,
            "image_role": "catalog_cover",
            "value": "storage baskets on catalog cover",
        },
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


def test_no_images_rejected_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post("/api/company-intake/photo", data={"source_platform": "mobile"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NO_IMAGES_UPLOADED"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CompanyImportJob)) == 0


def test_invalid_image_mime_is_rejected_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("note.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_TYPE"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CompanyImportJob)) == 0


def test_damaged_image_content_is_rejected_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("broken.png", b"not really a png", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE_CONTENT"
    assert fake.calls == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CompanyImportJob)) == 0


def test_oversized_image_is_rejected_without_job(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path, max_mb=0.0001)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("large.png", b"x" * 512, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "IMAGE_TOO_LARGE"
    assert fake.calls == []
    assert not (tmp_path / "company-uploads").exists()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CompanyImportJob)) == 0


def test_too_many_images_rejected_before_file_write(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake
    files = [
        ("files", (f"company-{index}.png", _image_bytes("PNG"), "image/png"))
        for index in range(5)
    ]

    response = client.post("/api/company-intake/photo", files=files)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TOO_MANY_IMAGES"
    assert fake.calls == []
    assert not (tmp_path / "company-uploads").exists()
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CompanyImportJob)) == 0


def test_company_photo_upload_creates_job_assets_and_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        data={
            "source_platform": "mobile",
            "image_roles": ["business_license", "catalog_cover"],
        },
        files=[
            ("files", ("../../license.png", _image_bytes("PNG"), "image/png")),
            ("files", ("catalog.jpg", _image_bytes("JPEG"), "image/jpeg")),
        ],
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready"
    assert payload["low_confidence"] is False
    assert payload["ai_result_type"] == "real_qwen"
    assert payload["ai_fallback_used"] is False
    assert payload["model_used"] == "qwen-vl-test"
    assert len(payload["assets"]) == 2
    assert payload["asset"]["image_role"] == "business_license"
    assert payload["draft"]["company_name"] == "Suzhou Export Pilot Co"
    assert payload["draft"]["target_countries"] == ["US", "JP"]
    assert ".." not in payload["asset"]["file_name"]
    assert "license.png" not in payload["asset"]["file_name"]
    assert "file_path" not in response.text
    assert "secret-token" not in response.text
    assert len(fake.calls) == 1
    assert fake.calls[0]["json_mode"] is True

    with session_factory() as db:
        job = db.get(CompanyImportJob, payload["import_job_id"])
        draft = db.get(CompanyDraft, payload["draft_id"])
        assert job is not None and job.status == "draft_ready"
        assert draft is not None
        assert draft.credit_code_suffix == "DE12"
        assert draft.target_countries == ["US", "JP"]
        assert draft.evidence is not None
        assert draft.evidence[0]["image_index"] == 0
        assert draft.evidence[0]["image_role"] == "business_license"
        assert draft.evidence[1]["image_index"] == 1
        assert draft.evidence[1]["image_role"] == "catalog_cover"
        assert db.scalar(select(func.count()).select_from(Company)) == 0


def test_vision_disabled_creates_low_confidence_manual_draft_without_ai_call(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, _session_factory = client_with_session
    monkeypatch.setenv("COMPANY_UPLOAD_DIR", str(tmp_path / "company-uploads"))
    monkeypatch.setenv("MAX_COMPANY_IMAGE_SIZE_MB", "10")
    monkeypatch.setenv("BAILIAN_VISION_ENABLED", "false")
    monkeypatch.setenv("BAILIAN_VISION_MODEL", "qwen-vl-test")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-key")
    get_settings.cache_clear()
    fake = FakeVisionClient(_success_json())
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("company.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["error_code"] == "BAILIAN_VISION_DISABLED"
    assert payload["next_action"] == "manual_fill"
    assert payload["ai_result_type"] == "fallback"
    assert payload["ai_fallback_used"] is True
    assert payload["draft"]["company_name"] is None
    assert fake.calls == []


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        ("not json", "AI_RESPONSE_PARSE_ERROR"),
        (json.dumps({"company_name": "Missing confidence"}), "AI_RESPONSE_SCHEMA_ERROR"),
    ],
)
def test_invalid_ai_response_creates_fallback_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    content: str,
    expected_code: str,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(content)
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("company.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["error_code"] == expected_code
    assert payload["ai_result_type"] == "fallback"
    assert payload["ai_fallback_used"] is True
    assert payload["draft"]["company_name"] is None
    assert len(fake.calls) == 1
    with session_factory() as db:
        draft = db.get(CompanyDraft, payload["draft_id"])
        assert draft is not None
        assert draft.confidence_score == 0


def test_low_confidence_ai_response_creates_reviewable_draft_without_company(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    low_confidence_payload = {
        **SUCCESS_PAYLOAD,
        "company_name": None,
        "industry": "Possible home goods manufacturer",
        "main_products": ["storage baskets"],
        "target_countries": ["US"],
        "confidence_score": 0.42,
        "risk_notes": ["Company name was not visible; user must confirm manually."],
        "evidence": [
            {
                "field": "industry",
                "source": "photo_visual",
                "image_index": 0,
                "image_role": "catalog_cover",
                "value": "catalog shows home storage products",
            }
        ],
    }
    fake = FakeVisionClient(json.dumps(low_confidence_payload, ensure_ascii=False))
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        data={"image_roles": ["catalog_cover"]},
        files={"files": ("company.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["low_confidence"] is True
    assert payload["ai_result_type"] == "manual_required"
    assert payload["ai_fallback_used"] is False
    assert payload["draft"]["company_name"] is None
    assert payload["draft"]["industry"] == "Possible home goods manufacturer"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Company)) == 0
        draft = db.get(CompanyDraft, payload["draft_id"])
        assert draft is not None
        assert draft.target_countries == ["US"]


def test_ai_timeout_returns_sanitized_low_confidence_draft(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    fake = FakeVisionClient(exc=BailianTimeoutError("Authorization: Bearer sentinel-secret"))
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("company.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_status"] == "draft_ready_with_low_confidence"
    assert payload["error_code"] == "BAILIAN_TIMEOUT"
    assert payload["error_message"] == (
        "Vision analysis is unavailable or returned unusable company intake output; "
        "please manually review the company draft."
    )
    assert "sentinel-secret" not in response.text
    assert "Authorization" not in response.text
    assert "Bearer" not in response.text
    with session_factory() as db:
        draft = db.get(CompanyDraft, payload["draft_id"])
        assert draft is not None
        assert draft.confidence_score == 0


def test_company_photo_privacy_is_redacted_in_response_and_db(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, session_factory = client_with_session
    _configure_intake_env(monkeypatch, tmp_path)
    sensitive_payload = {
        **SUCCESS_PAYLOAD,
        "company_name": "Suzhou Export Pilot Co 13812345678",
        "description": "Contact 13812345678 id 320311199001011234 email user@example.com",
        "risk_notes": ["Full code 91320506MA1ABCDE12 and bank 6222020202020202020 were visible."],
        "evidence": [
            {
                "field": "company_name",
                "source": "photo_text",
                "image_index": 0,
                "image_role": "business_license",
                "value": (
                    "Suzhou Export Pilot Co 13812345678 320311199001011234 "
                    "91320506MA1ABCDE12 user@example.com C:\\Users\\demo\\secret.png"
                ),
            }
        ],
    }
    fake = FakeVisionClient(json.dumps(sensitive_payload, ensure_ascii=False))
    app.dependency_overrides[get_bailian_client] = lambda: fake

    response = client.post(
        "/api/company-intake/photo",
        files={"files": ("company.png", _image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 201
    draft_response = client.get(f"/api/company-intake/drafts/{response.json()['draft_id']}")
    assert draft_response.status_code == 200
    combined_response_text = response.text + draft_response.text
    for raw in [
        "13812345678",
        "320311199001011234",
        "91320506MA1ABCDE12",
        "6222020202020202020",
        "user@example.com",
        "C:\\Users\\demo\\secret.png",
    ]:
        assert raw not in combined_response_text
    assert "[REDACTED_PHONE]" in combined_response_text
    assert "[REDACTED_EMAIL]" in combined_response_text

    with session_factory() as db:
        draft = db.get(CompanyDraft, response.json()["draft_id"])
        assert draft is not None
        stored_text = json.dumps(
            {
                "company_name": draft.company_name,
                "description": draft.description,
                "risk_notes": draft.risk_notes,
                "evidence": draft.evidence,
            },
            ensure_ascii=False,
            default=str,
        )
        for raw in [
            "13812345678",
            "320311199001011234",
            "91320506MA1ABCDE12",
            "6222020202020202020",
            "user@example.com",
            "C:\\Users\\demo\\secret.png",
        ]:
            assert raw not in stored_text
        assert draft.credit_code_suffix == "DE12"


class FakeVisionClient:
    def __init__(self, content: str | None = None, *, exc: Exception | None = None) -> None:
        self.content = content or _success_json()
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    async def vision_chat(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
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
    max_mb: float = 10,
) -> None:
    monkeypatch.setenv("COMPANY_UPLOAD_DIR", str(tmp_path / "company-uploads"))
    monkeypatch.setenv("MAX_COMPANY_IMAGE_SIZE_MB", str(max_mb))
    monkeypatch.setenv("BAILIAN_VISION_ENABLED", "true")
    monkeypatch.setenv("BAILIAN_VISION_MODEL", "qwen-vl-test")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fake-secret-key")
    get_settings.cache_clear()


def _image_bytes(image_format: str) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (32, 24), color=(40, 120, 180))
    image.save(output, format=image_format)
    return output.getvalue()


def _success_json() -> str:
    return json.dumps(SUCCESS_PAYLOAD, ensure_ascii=False)
