from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint, create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models
from app.db.base import Base
from app.models import (
    AnalysisCountryPreset,
    AnalysisRun,
    ChatMessage,
    ChatSession,
    Company,
    CompanyDraft,
    CompanyImportAsset,
    CompanyImportJob,
    Product,
    ProductDraft,
    ProductImportAsset,
    ProductImportJob,
    Report,
    ReportEditProposal,
    ReportVersion,
    TargetCountry,
)
from app.schemas import (
    AnalysisCountryPresetCreate,
    ChatMessageRead,
    CompanyDraftRead,
    CompanyDraftUpdateRequest,
    CompanyImportAssetRead,
    ProductDraftRead,
    ProductImportAssetRead,
    ReportEditProposalCreate,
    ReportEditProposalRead,
    ReportVersionRead,
    TargetCountryCreate,
)
from app.schemas.reports import ReportCreate
from app.services import report_service

_ = _models


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)


def test_q41_metadata_contains_new_tables_columns_and_constraints(
    session_factory: sessionmaker[Session],
) -> None:
    engine = session_factory.kw["bind"]
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "company_import_jobs",
        "company_import_assets",
        "company_drafts",
        "target_countries",
        "analysis_country_presets",
        "chat_sessions",
        "chat_messages",
        "report_versions",
        "report_edit_proposals",
    }.issubset(table_names)

    product_asset_columns = _column_names(inspector, "product_import_assets")
    assert {"image_index", "image_role", "is_primary"}.issubset(product_asset_columns)

    product_draft_columns = _column_names(inspector, "product_drafts")
    assert {"image_count", "primary_image_asset_id", "multi_image_summary"}.issubset(product_draft_columns)

    report_columns = _column_names(inspector, "reports")
    assert "current_version_id" in report_columns

    proposal_fk_targets = {
        fk["referred_table"]
        for fk in inspector.get_foreign_keys("report_edit_proposals")
        if fk["constrained_columns"] == ["accepted_version_id"]
    }
    assert proposal_fk_targets == {"report_versions"}

    assert _has_unique_constraint(TargetCountry.__table__, "country_code")
    assert _has_unique_constraint(AnalysisCountryPreset.__table__, "preset_code")
    assert _has_unique_constraint(ReportVersion.__table__, "report_id", "version_number")


def test_q41_models_insert_representative_graph_and_enforce_bounds(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        graph = _seed_representative_graph(db)
        assert graph["product_draft"].image_count == 2
        assert graph["product_draft"].primary_image_asset_id == graph["product_asset"].id
        assert graph["company_draft"].confidence_score == Decimal("0.7800")
        assert graph["preset"].country_codes == ["US", "JP"]
        assert graph["chat_message"].report_edit_proposal_id == graph["proposal"].id
        assert graph["proposal"].accepted_version_id == graph["version2"].id
        assert graph["report"].current_version_id == graph["version2"].id

        db.add(
            ProductDraft(
                import_job_id=graph["product_job"].id,
                company_id=graph["company"].id,
                image_count=-1,
                status="draft",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            ReportEditProposal(
                report_id=graph["report"].id,
                target_version_id=graph["version1"].id,
                user_intent="invalid confidence",
                confidence_score=Decimal("1.5000"),
                status="draft",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_q41_pydantic_schemas_serialize_and_validate(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        graph = _seed_representative_graph(db)

        product_asset_payload = ProductImportAssetRead.model_validate(graph["product_asset"]).model_dump()
        company_asset_payload = CompanyImportAssetRead.model_validate(graph["company_asset"]).model_dump()
        product_draft_payload = ProductDraftRead.model_validate(graph["product_draft"]).model_dump()
        company_draft_payload = CompanyDraftRead.model_validate(graph["company_draft"]).model_dump()
        chat_payload = ChatMessageRead.model_validate(graph["chat_message"]).model_dump()
        version_payload = ReportVersionRead.model_validate(graph["version1"]).model_dump()
        proposal_payload = ReportEditProposalRead.model_validate(graph["proposal"]).model_dump()

        assert "file_path" not in product_asset_payload
        assert "file_path" not in company_asset_payload
        assert product_asset_payload["image_role"] == "main"
        assert company_asset_payload["image_role"] == "business_license"
        assert product_draft_payload["image_count"] == 2
        assert company_draft_payload["low_confidence"] is False
        assert chat_payload["report_edit_proposal_id"] == graph["proposal"].id
        assert version_payload["version_number"] == 1
        assert proposal_payload["status"] == "accepted"

    country = TargetCountryCreate(
        country_code=" us ",
        name_cn="美国",
        name_en="United States",
        region_code=" north_america ",
        languages=["English", "english", ""],
    )
    assert country.country_code == "US"
    assert country.region_code == "NORTH_AMERICA"
    assert country.languages == ["English"]

    preset = AnalysisCountryPresetCreate(
        preset_code=" demo ",
        name_cn="演示默认国家",
        country_codes=["us", "JP", "us"],
    )
    assert preset.preset_code == "DEMO"
    assert preset.country_codes == ["US", "JP"]

    with pytest.raises(ValidationError):
        AnalysisCountryPresetCreate(preset_code="bad", name_cn="bad", country_codes=["usa1"])

    with pytest.raises(ValidationError):
        CompanyDraftUpdateRequest(confidence_score=Decimal("1.2000"))

    with pytest.raises(ValidationError):
        ReportEditProposalCreate(
            report_id=1,
            user_intent="invalid confidence",
            confidence_score=Decimal("-0.0100"),
        )


def test_report_service_creates_initial_version(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        company = Company(name="Version Service Co", region="Jiangsu", industry="Home goods")
        db.add(company)
        db.flush()
        analysis = AnalysisRun(company_id=company.id, status="success", target_countries=["US"])
        db.add(analysis)
        db.flush()

        report = report_service.create_report(
            db,
            ReportCreate(
                analysis_id=analysis.id,
                company_id=company.id,
                title="Generated Report",
                content_markdown="# Generated Report",
                content_html="<article>Generated Report</article>",
            ),
        )

        version = db.scalar(select(ReportVersion).where(ReportVersion.report_id == report.id))
        assert version is not None
        assert version.version_number == 1
        assert report.current_version_id == version.id
        assert report.content_markdown == version.content_markdown


def test_q41_migration_revision_metadata_and_required_ddls() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260604_0008_q41_upgrade_database_models.py"
    )
    module = _load_module_from_path(migration_path)
    source = migration_path.read_text(encoding="utf-8")

    assert module.revision == "20260604_0008"
    assert module.down_revision == "20260529_0007"
    for required in [
        "product_import_assets",
        "image_index",
        "product_drafts",
        "primary_image_asset_id",
        "company_import_jobs",
        "company_import_assets",
        "company_drafts",
        "target_countries",
        "analysis_country_presets",
        "chat_sessions",
        "chat_messages",
        "report_versions",
        "report_edit_proposals",
        "current_version_id",
        "Backfilled from reports table.",
    ]:
        assert required in source


def _seed_representative_graph(db: Session) -> dict[str, object]:
    company = Company(
        name="Q41 Model Co",
        region="Jiangsu",
        industry="Home goods",
        description="Database model test company.",
        target_countries=["US", "JP"],
    )
    db.add(company)
    db.flush()

    product = Product(
        company_id=company.id,
        product_name_cn="多图测试产品",
        product_name_en="Multi Image Product",
        category="Home goods",
    )
    db.add(product)
    db.flush()

    product_job = ProductImportJob(
        company_id=company.id,
        source_type="multi_image",
        source_platform="jd",
        status="draft_ready",
        model_used="qwen-vl",
    )
    db.add(product_job)
    db.flush()
    product_asset = ProductImportAsset(
        import_job_id=product_job.id,
        file_name="main.png",
        file_path="C:/private/product/main.png",
        mime_type="image/png",
        file_size=1024,
        width=800,
        height=600,
        image_index=0,
        image_role="main",
        is_primary=True,
    )
    detail_asset = ProductImportAsset(
        import_job_id=product_job.id,
        file_name="detail.png",
        file_path="C:/private/product/detail.png",
        mime_type="image/png",
        file_size=2048,
        width=900,
        height=700,
        image_index=1,
        image_role="detail",
        is_primary=False,
    )
    db.add_all([product_asset, detail_asset])
    db.flush()
    product_draft = ProductDraft(
        import_job_id=product_job.id,
        company_id=company.id,
        product_name_cn="多图测试产品",
        category="Home goods",
        evidence=[{"field": "product_name_cn", "asset_id": product_asset.id, "confidence": 0.9}],
        confidence_score=Decimal("0.9100"),
        image_count=2,
        primary_image_asset_id=product_asset.id,
        multi_image_summary={"conflicts": ["material requires manual review"]},
        status="draft",
    )
    db.add(product_draft)

    company_job = CompanyImportJob(
        source_type="photo",
        source_platform="mobile",
        status="draft_ready",
        model_used="qwen-vl",
    )
    db.add(company_job)
    db.flush()
    company_asset = CompanyImportAsset(
        import_job_id=company_job.id,
        file_name="license.jpg",
        file_path="C:/private/company/license.jpg",
        mime_type="image/jpeg",
        file_size=4096,
        width=1200,
        height=900,
        image_index=0,
        image_role="business_license",
        is_primary=True,
    )
    company_draft = CompanyDraft(
        import_job_id=company_job.id,
        company_name="Q41 Model Co",
        credit_code_suffix="1234",
        region="Jiangsu",
        industry="Home goods",
        main_products=["storage basket"],
        contact_role="sales manager",
        evidence=[{"field": "company_name", "asset_id": company_asset.id, "confidence": 0.8}],
        risk_notes=["AI extraction is not qualification verification."],
        confidence_score=Decimal("0.7800"),
        status="draft",
        confirmed_company_id=company.id,
    )
    db.add_all([company_asset, company_draft])

    country = TargetCountry(
        country_code="US",
        name_cn="美国",
        name_en="United States",
        region_code="NORTH_AMERICA",
        region_name_cn="北美",
        region_name_en="North America",
        continent="North America",
        currency_code="USD",
        languages=["English"],
        default_sort_order=1,
        enabled=True,
        analysis_enabled=True,
        provider_mappings={"worldbank": {"country_code": "USA"}},
        fallback_enabled=True,
    )
    preset = AnalysisCountryPreset(
        preset_code="DEMO_DEFAULT",
        name_cn="演示默认国家",
        country_codes=["US", "JP"],
        is_default=True,
        enabled=True,
    )
    db.add_all([country, preset])

    analysis = AnalysisRun(company_id=company.id, status="success", target_countries=["US"])
    db.add(analysis)
    db.flush()
    report = Report(
        analysis_id=analysis.id,
        company_id=company.id,
        title="Q41 Report",
        content_markdown="# Q41 Report",
        content_html="<article>Q41 Report</article>",
    )
    db.add(report)
    db.flush()
    version1 = ReportVersion(
        report_id=report.id,
        version_number=1,
        content_markdown=report.content_markdown,
        content_html=report.content_html,
        source_type="generated",
        created_by="system",
    )
    db.add(version1)
    db.flush()
    report.current_version_id = version1.id

    chat_session = ChatSession(
        title="Report edit",
        current_page="reports",
        company_id=company.id,
        product_id=product.id,
        analysis_id=analysis.id,
        report_id=report.id,
        context_refs={"report_id": report.id, "version_id": version1.id},
        safety_status="safe",
        status="active",
    )
    db.add(chat_session)
    db.flush()
    proposal = ReportEditProposal(
        report_id=report.id,
        target_version_id=version1.id,
        source_chat_session_id=chat_session.id,
        user_intent="Strengthen the risk section.",
        proposed_markdown="# Q41 Report\n\nUpdated risk section.",
        diff={"replace": [{"section": "risk"}]},
        risk_notes=["User review required before saving a new version."],
        evidence=[{"version_id": version1.id, "section": "risk"}],
        confidence_score=Decimal("0.8200"),
        status="accepted",
    )
    db.add(proposal)
    db.flush()
    chat_message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content="Created a report edit proposal.",
        content_redacted=True,
        context_refs={"proposal_id": proposal.id},
        safety_status="safe",
        model_used="qwen3.6-plus",
        report_edit_proposal_id=proposal.id,
    )
    version2 = ReportVersion(
        report_id=report.id,
        version_number=2,
        parent_version_id=version1.id,
        content_markdown=proposal.proposed_markdown,
        content_html="<article>Updated risk section.</article>",
        source_type="proposal",
        source_proposal_id=proposal.id,
        created_by="user",
        version_note="Accepted proposal.",
    )
    db.add_all([chat_message, version2])
    db.flush()
    proposal.accepted_version_id = version2.id
    report.current_version_id = version2.id
    db.commit()

    return {
        "company": company,
        "product": product,
        "product_job": product_job,
        "product_asset": product_asset,
        "product_draft": product_draft,
        "company_asset": company_asset,
        "company_draft": company_draft,
        "preset": preset,
        "report": report,
        "version1": version1,
        "version2": version2,
        "proposal": proposal,
        "chat_message": chat_message,
    }


def _column_names(inspector: object, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _has_unique_constraint(table: object, *columns: str) -> bool:
    expected = set(columns)
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == expected
        for constraint in table.constraints
    )


def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("q41_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
