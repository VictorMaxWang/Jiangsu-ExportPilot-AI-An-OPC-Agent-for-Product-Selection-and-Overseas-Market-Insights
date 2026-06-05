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
from app.models import Company, Product, ProductDraft, ProductImportJob, ProductKeyword

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


def test_list_drafts_filters_by_company_status_platform_and_paginates(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory, name="Draft Filter Co")
    other_company_id = _seed_company(session_factory, name="Other Draft Co")
    first_id = _seed_draft(session_factory, company_id, source_platform="jd")
    second_id = _seed_draft(session_factory, company_id, source_platform="taobao", product_name_cn="棉拖鞋")
    _seed_draft(session_factory, company_id, status="confirmed", source_platform="taobao", product_name_cn="已确认")
    _seed_draft(session_factory, other_company_id, source_platform="taobao", product_name_cn="其他公司")

    page = client.get(f"/api/product-intake/drafts?company_id={company_id}&status=draft&limit=1&offset=0")
    second_page = client.get(f"/api/product-intake/drafts?company_id={company_id}&status=draft&limit=1&offset=1")
    platform_page = client.get(f"/api/product-intake/drafts?company_id={company_id}&source_platform=taobao")

    assert page.status_code == 200
    payload = page.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert [item["id"] for item in payload["items"]] == [second_id]
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [first_id]
    assert platform_page.status_code == 200
    assert {item["product_name_cn"] for item in platform_page.json()["items"]} == {"棉拖鞋", "已确认"}


def test_update_draft_edits_allowed_fields_and_risk_notes(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(session_factory, company_id)

    response = client.put(
        f"/api/product-intake/drafts/{draft_id}",
        json={
            "product_name_cn": "  宠物冰垫升级款  ",
            "product_name_en": "Upgraded Pet Cooling Mat",
            "category": "Pet Supplies",
            "price_cny": "49.90",
            "cost_price_cny": "23.50",
            "weight_kg": "0.650",
            "package_size": "30x20x5cm",
            "material": "尼龙",
            "color_options": ["蓝色", "蓝色", "绿色"],
            "specification": "尺寸 30x20cm，适合夏季使用",
            "selling_points": {
                "selling_points_cn": ["凉感面料"],
                "selling_points_en": ["Cooling fabric"],
                "usage_scenarios": ["home"],
                "cross_border_keywords_en": ["cooling pet mat"],
                "risk_notes": ["会被顶层风险备注覆盖"],
            },
            "target_users": ["pet owners", "pet owners"],
            "risk_notes": ["人工确认材质"],
            "confidence_score": "0.7200",
            "evidence": [
                {"field": "material", "source": "url_text", "value": "尼龙材质"},
                {
                    "field": "price_cny",
                    "source": "model_inference",
                    "image_index": 1,
                    "image_role": "detail",
                    "value": "参考价 49.90",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["product_name_cn"] == "宠物冰垫升级款"
    assert payload["price_cny"] == "49.90"
    assert payload["cost_price_cny"] == "23.50"
    assert payload["weight_kg"] == "0.650"
    assert payload["color_options"] == ["蓝色", "绿色"]
    assert payload["target_users"] == ["pet owners"]
    assert payload["selling_points"]["risk_notes"] == ["人工确认材质"]
    assert payload["selling_points"]["cross_border_keywords_en"] == ["cooling pet mat"]
    assert payload["confidence_score"] == "0.7200"
    assert payload["evidence"] == [
        {"field": "material", "source": "url_text", "value": "尼龙材质"},
        {
            "field": "price_cny",
            "source": "model_inference",
            "value": "参考价 49.90",
            "image_index": 1,
            "image_role": "detail",
        },
    ]

    with session_factory() as db:
        draft = db.get(ProductDraft, draft_id)
        assert draft is not None
        assert draft.material == "尼龙"
        assert draft.confidence_score == Decimal("0.7200")
        assert draft.evidence == [
            {"field": "material", "source": "url_text", "value": "尼龙材质"},
            {
                "field": "price_cny",
                "source": "model_inference",
                "value": "参考价 49.90",
                "image_index": 1,
                "image_role": "detail",
            },
        ]
        assert draft.selling_points is not None
        assert draft.selling_points["selling_points_cn"] == ["凉感面料"]

    combined = response.text
    assert "raw_text" not in combined
    assert "file_path" not in combined
    assert "secret-token" not in combined
    assert "Authorization" not in combined
    assert "Bearer" not in combined


def test_terminal_drafts_cannot_be_edited(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    confirmed_id = _seed_draft(session_factory, company_id, status="confirmed")
    rejected_id = _seed_draft(session_factory, company_id, status="rejected")

    confirmed_response = client.put(f"/api/product-intake/drafts/{confirmed_id}", json={"category": "Blocked"})
    rejected_response = client.put(f"/api/product-intake/drafts/{rejected_id}", json={"category": "Blocked"})
    forbidden_field_response = client.put(f"/api/product-intake/drafts/{rejected_id}", json={"status": "draft"})

    assert confirmed_response.status_code == 409
    assert rejected_response.status_code == 409
    assert forbidden_field_response.status_code == 422


def test_missing_job_draft_and_update_return_404(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = client_with_session

    job_response = client.get("/api/product-intake/jobs/99999")
    draft_response = client.get("/api/product-intake/drafts/99999")
    update_response = client.put("/api/product-intake/drafts/99999", json={"product_name_cn": "不存在"})

    assert job_response.status_code == 404
    assert draft_response.status_code == 404
    assert update_response.status_code == 404
    assert update_response.json()["detail"]["code"] == "DRAFT_NOT_FOUND"


def test_confirm_draft_requires_product_name_cn_and_rolls_back(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(session_factory, company_id, product_name_cn=None)

    response = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "DRAFT_CONFIRMATION_VALIDATION_FAILED"
    with session_factory() as db:
        draft = db.get(ProductDraft, draft_id)
        assert draft is not None
        assert draft.status == "draft"
        assert draft.confirmed_product_id is None
        assert db.scalar(select(func.count()).select_from(Product)) == 0


def test_confirm_draft_creates_product_updates_job_and_persists_keywords(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(session_factory, company_id, cost_price_cny=None, price_cny=Decimal("39.90"))

    response = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == company_id
    assert payload["product_name_cn"] == "宠物凉感垫"
    assert payload["product_name_en"] == "Pet Cooling Mat"
    assert payload["cost_price_cny"] is None
    assert "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。" in payload["description"]
    assert "AI 识别置信度" in payload["description"]
    assert "参考价格" in payload["description"]
    assert "非采购成本" in payload["description"]
    assert "secret-token" not in response.text
    assert "raw_text" not in response.text
    assert "file_path" not in response.text
    assert "Authorization" not in response.text
    assert "Bearer" not in response.text

    with session_factory() as db:
        product = db.get(Product, payload["id"])
        draft = db.get(ProductDraft, draft_id)
        job = db.get(ProductImportJob, draft.import_job_id if draft is not None else 0)
        keywords = list(
            db.scalars(
                select(ProductKeyword.keyword).where(ProductKeyword.product_id == payload["id"]).order_by(ProductKeyword.id)
            )
        )
        keyword_rows = list(db.scalars(select(ProductKeyword).where(ProductKeyword.product_id == payload["id"])))

        assert product is not None
        assert product.cost_price_cny is None
        assert draft is not None and draft.status == "confirmed"
        assert draft.confirmed_product_id == product.id
        assert job is not None and job.status == "confirmed"
        assert keywords == ["pet cooling pad", "summer pet mat", "Pet Cooling Mat"]
        assert {row.language for row in keyword_rows} == {"en"}
        assert {row.country for row in keyword_rows} == {None}
        assert {row.source for row in keyword_rows} == {"product_intake_confirmed"}


def test_confirmed_draft_cannot_be_confirmed_or_rejected_again(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(session_factory, company_id)

    first = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})
    repeated = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})
    reject = client.post(f"/api/product-intake/drafts/{draft_id}/reject", json={"company_id": company_id})

    assert first.status_code == 200
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "DRAFT_ALREADY_CONFIRMED"
    assert reject.status_code == 409
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Product)) == 1
        assert db.scalar(select(func.count()).select_from(ProductKeyword)) == 3


def test_reject_draft_blocks_confirm_and_does_not_create_product(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(session_factory, company_id)

    rejected = client.post(
        f"/api/product-intake/drafts/{draft_id}/reject",
        json={"company_id": company_id, "reason": "  不适合本次选品  "},
    )
    confirm = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})
    rejected_again = client.post(f"/api/product-intake/drafts/{draft_id}/reject", json={"company_id": company_id})

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["confirmed_product_id"] is None
    assert rejected.json()["selling_points"]["risk_notes"][-1] == "拒绝原因：不适合本次选品"
    assert confirm.status_code == 409
    assert confirm.json()["detail"]["code"] == "DRAFT_ALREADY_REJECTED"
    assert rejected_again.status_code == 409

    with session_factory() as db:
        draft = db.get(ProductDraft, draft_id)
        job = db.get(ProductImportJob, draft.import_job_id if draft is not None else 0)
        assert draft is not None and draft.status == "rejected"
        assert job is not None and job.status == "draft_ready"
        assert db.scalar(select(func.count()).select_from(Product)) == 0


def test_confirm_reject_validate_company_scope(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    other_company_id = _seed_company(session_factory, name="Other Scope Co")
    draft_id = _seed_draft(session_factory, company_id)

    confirm = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": other_company_id})
    reject = client.post(f"/api/product-intake/drafts/{draft_id}/reject", json={"company_id": other_company_id})

    assert confirm.status_code == 404
    assert confirm.json()["detail"]["code"] == "DRAFT_NOT_FOUND"
    assert reject.status_code == 404
    assert reject.json()["detail"]["code"] == "DRAFT_NOT_FOUND"


def test_low_confidence_draft_can_be_edited_and_manually_confirmed(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    company_id = _seed_company(session_factory)
    draft_id = _seed_draft(
        session_factory,
        company_id,
        confidence_score=Decimal("0.4000"),
        product_name_cn=None,
        product_name_en=None,
        selling_points={"cross_border_keywords_en": ["manual cooling pad"]},
    )

    update = client.put(
        f"/api/product-intake/drafts/{draft_id}",
        json={
            "product_name_cn": "人工确认宠物垫",
            "product_name_en": "Manual Pet Mat",
            "cost_price_cny": "18.20",
        },
    )
    confirm = client.post(f"/api/product-intake/drafts/{draft_id}/confirm", json={"company_id": company_id})

    assert update.status_code == 200
    assert update.json()["low_confidence"] is True
    assert confirm.status_code == 200
    assert confirm.json()["product_name_cn"] == "人工确认宠物垫"
    assert confirm.json()["cost_price_cny"] == "18.20"
    with session_factory() as db:
        product = db.get(Product, confirm.json()["id"])
        assert product is not None
        assert product.cost_price_cny == Decimal("18.20")


def _seed_company(session_factory: sessionmaker[Session], *, name: str = "Nantong Draft Demo") -> int:
    with session_factory() as db:
        company = Company(
            name=name,
            region="Jiangsu",
            industry="Home textiles",
            description="Draft API test company",
            target_countries=["US", "JP"],
        )
        db.add(company)
        db.commit()
        return company.id


def _seed_draft(
    session_factory: sessionmaker[Session],
    company_id: int,
    *,
    status: str = "draft",
    source_platform: str = "jd",
    product_name_cn: str | None = "宠物凉感垫",
    product_name_en: str | None = "Pet Cooling Mat",
    price_cny: Decimal | None = Decimal("39.90"),
    cost_price_cny: Decimal | None = Decimal("21.50"),
    confidence_score: Decimal = Decimal("0.8200"),
    selling_points: dict[str, object] | None = None,
) -> int:
    with session_factory() as db:
        job = ProductImportJob(
            company_id=company_id,
            source_type="url",
            source_platform=source_platform,
            source_url="https://item.jd.com/100012043978.html?token=secret-token",
            status="draft_ready",
            raw_text="raw page text with token=secret-token",
        )
        db.add(job)
        db.flush()
        draft = ProductDraft(
            import_job_id=job.id,
            company_id=company_id,
            product_name_cn=product_name_cn,
            product_name_en=product_name_en,
            category="Pet supplies",
            price_cny=price_cny,
            cost_price_cny=cost_price_cny,
            weight_kg=Decimal("0.450"),
            package_size="28x18x4cm",
            material="尼龙",
            color_options=["蓝色"],
            specification="夏季宠物凉感垫",
            selling_points=selling_points
            or {
                "selling_points_cn": ["夏季降温"],
                "selling_points_en": ["Cooling mat for summer"],
                "usage_scenarios": ["home"],
                "cross_border_keywords_en": ["pet cooling pad", "Pet Cooling Pad", "summer pet mat"],
                "risk_notes": ["URL text requires manual review."],
            },
            target_users=["pet owners"],
            source_platform=source_platform,
            source_url="https://item.jd.com/100012043978.html?token=secret-token",
            evidence=[{"field": "product_name_cn", "source": "url_text", "value": "宠物凉感垫"}],
            confidence_score=confidence_score,
            status=status,
        )
        db.add(draft)
        db.commit()
        return draft.id
