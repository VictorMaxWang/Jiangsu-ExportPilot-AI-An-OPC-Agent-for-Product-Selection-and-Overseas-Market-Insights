from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import Company, CompanyDraft, CompanyImportJob

_ = _models


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
    Base.metadata.drop_all(bind=engine)


def test_list_drafts_filters_by_status_and_platform(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    first_id = _seed_draft(session_factory, source_platform="mobile", company_name="First Company")
    second_id = _seed_draft(session_factory, source_platform="catalog", company_name="Second Company")
    _seed_draft(session_factory, status="confirmed", source_platform="mobile", company_name="Confirmed Company")

    page = client.get("/api/company-intake/drafts?status=draft&limit=1&offset=0")
    second_page = client.get("/api/company-intake/drafts?status=draft&limit=1&offset=1")
    platform_page = client.get("/api/company-intake/drafts?source_platform=mobile")

    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert [item["id"] for item in page.json()["items"]] == [second_id]
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [first_id]
    assert platform_page.status_code == 200
    assert {item["company_name"] for item in platform_page.json()["items"]} == {"First Company", "Confirmed Company"}


def test_update_draft_sanitizes_fields_and_evidence(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    draft_id = _seed_draft(session_factory)

    response = client.put(
        f"/api/company-intake/drafts/{draft_id}",
        json={
            "company_name": "  Updated Company 13812345678  ",
            "credit_code_suffix": "91320506MA1ABCDE12",
            "region": "Jiangsu Nantong",
            "industry": "Textiles",
            "main_products": ["blanket", "blanket", "towel"],
            "target_countries": ["us", "JP", "bad-country", "us"],
            "website": "https://example.test/company?token=secret-token",
            "description": "Visible profile with phone 13812345678 and id 320311199001011234",
            "contact_role": "Sales contact",
            "risk_notes": ["Manual check 6222020202020202020"],
            "confidence_score": "0.7200",
            "evidence": [
                {
                    "field": "company_name",
                    "source": "manual_text",
                    "image_index": 0,
                    "image_role": "business_license",
                    "value": "Updated Company 13812345678 user@example.com",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["company_name"] == "Updated Company [REDACTED_PHONE]"
    assert payload["credit_code_suffix"] == "DE12"
    assert payload["main_products"] == ["blanket", "towel"]
    assert payload["target_countries"] == ["US", "JP"]
    assert payload["website"] == "https://example.test/company"
    assert payload["confidence_score"] == "0.7200"
    assert "13812345678" not in response.text
    assert "320311199001011234" not in response.text
    assert "6222020202020202020" not in response.text
    assert "user@example.com" not in response.text
    assert "secret-token" not in response.text

    with session_factory() as db:
        draft = db.get(CompanyDraft, draft_id)
        assert draft is not None
        assert draft.company_name == "Updated Company [REDACTED_PHONE]"
        assert draft.credit_code_suffix == "DE12"
        assert draft.target_countries == ["US", "JP"]


def test_confirm_draft_creates_company_updates_job_and_blocks_repeat(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    draft_id = _seed_draft(session_factory)

    response = client.post(f"/api/company-intake/drafts/{draft_id}/confirm")
    repeated = client.post(f"/api/company-intake/drafts/{draft_id}/confirm", json={})
    reject = client.post(f"/api/company-intake/drafts/{draft_id}/reject", json={"reason": "wrong company"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Nantong Export Co"
    assert payload["region"] == "Jiangsu Nantong"
    assert payload["industry"] == "Home textiles"
    assert payload["target_countries"] == ["US", "JP"]
    assert "Main products" in payload["description"]
    assert "blanket" in payload["description"]
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "DRAFT_ALREADY_CONFIRMED"
    assert reject.status_code == 409

    with session_factory() as db:
        draft = db.get(CompanyDraft, draft_id)
        job = db.get(CompanyImportJob, draft.import_job_id if draft is not None else 0)
        assert draft is not None and draft.status == "confirmed"
        assert draft.confirmed_company_id == payload["id"]
        assert job is not None and job.status == "confirmed"
        assert db.scalar(select(func.count()).select_from(Company)) == 1


def test_confirm_requires_company_name_and_rolls_back(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    draft_id = _seed_draft(session_factory, company_name=None, confidence_score=Decimal("0.4000"))

    response = client.post(f"/api/company-intake/drafts/{draft_id}/confirm")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "DRAFT_CONFIRMATION_VALIDATION_FAILED"
    with session_factory() as db:
        draft = db.get(CompanyDraft, draft_id)
        assert draft is not None and draft.status == "draft"
        assert draft.confirmed_company_id is None
        assert db.scalar(select(func.count()).select_from(Company)) == 0


def test_reject_draft_blocks_confirm_and_does_not_create_company(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    draft_id = _seed_draft(session_factory)

    rejected = client.post(
        f"/api/company-intake/drafts/{draft_id}/reject",
        json={"reason": "  duplicate 13812345678  "},
    )
    confirm = client.post(f"/api/company-intake/drafts/{draft_id}/confirm")
    rejected_again = client.post(f"/api/company-intake/drafts/{draft_id}/reject", json={})

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["confirmed_company_id"] is None
    assert "13812345678" not in rejected.text
    assert rejected.json()["risk_notes"][-1] == "Reject reason: duplicate [REDACTED_PHONE]"
    assert confirm.status_code == 409
    assert confirm.json()["detail"]["code"] == "DRAFT_ALREADY_REJECTED"
    assert rejected_again.status_code == 409

    with session_factory() as db:
        draft = db.get(CompanyDraft, draft_id)
        assert draft is not None and draft.status == "rejected"
        assert db.scalar(select(func.count()).select_from(Company)) == 0


def test_terminal_drafts_cannot_be_edited(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    confirmed_id = _seed_draft(session_factory, status="confirmed")
    rejected_id = _seed_draft(session_factory, status="rejected")

    confirmed_response = client.put(f"/api/company-intake/drafts/{confirmed_id}", json={"industry": "Blocked"})
    rejected_response = client.put(f"/api/company-intake/drafts/{rejected_id}", json={"industry": "Blocked"})
    forbidden_field_response = client.put(f"/api/company-intake/drafts/{rejected_id}", json={"status": "draft"})

    assert confirmed_response.status_code == 409
    assert rejected_response.status_code == 409
    assert forbidden_field_response.status_code == 422


def test_missing_job_draft_and_update_return_404(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    job_response = client.get("/api/company-intake/jobs/99999")
    draft_response = client.get("/api/company-intake/drafts/99999")
    update_response = client.put("/api/company-intake/drafts/99999", json={"company_name": "Missing"})

    assert job_response.status_code == 404
    assert draft_response.status_code == 404
    assert update_response.status_code == 404
    assert update_response.json()["detail"]["code"] == "DRAFT_NOT_FOUND"


def _seed_draft(
    session_factory: sessionmaker[Session],
    *,
    status: str = "draft",
    source_platform: str = "mobile",
    company_name: str | None = "Nantong Export Co",
    confidence_score: Decimal = Decimal("0.8200"),
) -> int:
    with session_factory() as db:
        job = CompanyImportJob(
            source_type="photo",
            source_platform=source_platform,
            status="draft_ready",
            model_used="qwen-vl-test",
        )
        db.add(job)
        db.flush()
        draft = CompanyDraft(
            import_job_id=job.id,
            company_name=company_name,
            credit_code_suffix="1234",
            region="Jiangsu Nantong",
            industry="Home textiles",
            main_products=["blanket", "towel"],
            target_countries=["US", "JP"],
            website="https://example.test/company",
            description="Visible company profile from uploaded material.",
            contact_role="export sales",
            evidence=[
                {
                    "field": "company_name",
                    "source": "photo_text",
                    "image_index": 0,
                    "image_role": "business_license",
                    "value": company_name,
                }
            ],
            risk_notes=["Manual review required."],
            confidence_score=confidence_score,
            status=status,
        )
        db.add(draft)
        db.commit()
        return draft.id
