from __future__ import annotations

import json
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ai import get_bailian_client
from app.db import get_db
from app.db.base import Base
from app.main import app
from app.models import AnalysisRun, ChatMessage, Company, OpportunityScore, Product, Report, ReportEditProposal, ReportVersion
from app.schemas import ReportCreate
from app.services import report_service
from app.services.ai import BailianChatCompletion, BailianConfigurationError


def test_chat_session_create_and_list_supports_page_context_and_ids(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    graph = _seed_chat_graph(session_factory)

    response = client.post(
        "/api/chat/sessions",
        json={
            "current_page": "reports/detail",
            "report_id": graph["report_id"],
            "product_id": graph["product_id"],
            "page_context": {
                "route": f"/reports/{graph['report_id']}",
                "panel": "summary",
                "secret": "api_key=secret-token",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["report_id"] == graph["report_id"]
    assert payload["analysis_id"] == graph["analysis_id"]
    assert payload["company_id"] == graph["company_id"]
    assert payload["product_id"] == graph["product_id"]
    assert payload["page_context"]["route"] == f"/reports/{graph['report_id']}"
    assert payload["page_context"]["secret"] == "[REDACTED]"

    list_response = client.get(f"/api/chat/sessions?report_id={graph['report_id']}")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == payload["id"]


def test_send_message_persists_messages_and_builds_redacted_compact_context(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    graph = _seed_chat_graph(session_factory, report_suffix="LONG-CONTEXT " * 2000)
    session_id = _create_session(client, graph)
    stub = StubBailianClient(
        json.dumps(
            {
                "assistant_message": "美国优先级较高，主要来自总分、内容主题和供应侧匹配；风险是样本数据需要复核。",
                "intent": "explain_recommendation",
                "proposal": None,
            },
            ensure_ascii=False,
        )
    )
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={
                "role": "user",
                "content": "Explain the recommendation reason and product risk.",
                "page_context": {"tab": "risk", "token": "secret-token"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_message"]["role"] == "user"
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["assistant_message"]["model_used"] == "qwen3.6-plus"
    assert payload["assistant_message"]["token_count"] == 88
    assert payload["assistant_message"]["error_code"] is None
    assert payload["session"]["last_message_at"] is not None

    prompt_payload = json.loads(stub.messages[1]["content"])
    serialized_prompt = json.dumps(prompt_payload, ensure_ascii=False)
    assert "Q49 Throw Blanket" in serialized_prompt
    assert "source gap" in serialized_prompt
    assert "secret-token" not in serialized_prompt
    assert "api_key=" not in serialized_prompt
    assert len(serialized_prompt) < 20000
    assert prompt_payload["context_budget"]["context_truncated"] is True

    messages_response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ChatMessage)) == 2


def test_report_edit_message_creates_proposal_without_overwriting_report(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    graph = _seed_chat_graph(session_factory)
    session_id = _create_session(client, graph)
    proposed_markdown = "# Q49 Report\n\n## Risk\nAdd a clearer certification review caveat."
    stub = StubBailianClient(
        json.dumps(
            {
                "assistant_message": "已生成报告修改 proposal，原报告不会被覆盖。",
                "intent": "report_edit_proposal",
                "proposal": {
                    "user_intent": "Strengthen the risk section.",
                    "proposed_markdown": proposed_markdown,
                    "diff": {"summary": "Strengthen risk caveat", "changes": ["Add certification review caveat"]},
                    "replacement_blocks": [
                        {
                            "section": "Risk",
                            "before_summary": "Risk section was brief.",
                            "after_markdown": "Add a clearer certification review caveat.",
                        }
                    ],
                    "risk_notes": ["Human review required before accepting."],
                    "evidence": [{"source": "report", "detail": "risk section"}],
                    "confidence_score": 0.82,
                },
            },
            ensure_ascii=False,
        )
    )
    with session_factory() as db:
        original_report = db.get(Report, graph["report_id"])
        assert original_report is not None
        original_markdown = original_report.content_markdown
        original_version_id = original_report.current_version_id

    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "请修改这份报告的风险提示，让答辩时更稳妥。"},
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal"] is not None
    assert payload["proposal"]["status"] == "draft"
    assert payload["proposal"]["proposed_markdown"] == proposed_markdown
    assert payload["assistant_message"]["report_edit_proposal_id"] == payload["proposal"]["id"]

    with session_factory() as db:
        report = db.get(Report, graph["report_id"])
        assert report is not None
        assert report.content_markdown == original_markdown
        assert report.current_version_id == original_version_id
        assert db.scalar(select(func.count()).select_from(ReportVersion).where(ReportVersion.report_id == report.id)) == 1
        proposal = db.get(ReportEditProposal, payload["proposal"]["id"])
        assert proposal is not None
        assert proposal.target_version_id == original_version_id
        assert proposal.proposed_html and "<article" in proposal.proposed_html


def test_chat_context_missing_and_mismatched_ids_return_safe_errors(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    graph = _seed_chat_graph(session_factory)
    other_product_id = _seed_other_product(session_factory)

    missing = client.post("/api/chat/sessions", json={"report_id": 999999})
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "REPORT_NOT_FOUND"

    mismatch = client.post(
        "/api/chat/sessions",
        json={"analysis_id": graph["analysis_id"], "product_id": other_product_id},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "CHAT_CONTEXT_MISMATCH"


def test_bailian_error_persists_degraded_sanitized_assistant_message(
    client_with_session: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = client_with_session
    graph = _seed_chat_graph(session_factory)
    session_id = _create_session(client, graph)
    stub = ErrorBailianClient()
    app.dependency_overrides[get_bailian_client] = lambda: stub
    try:
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"role": "user", "content": "Explain this report."},
        )
    finally:
        app.dependency_overrides.pop(get_bailian_client, None)

    assert response.status_code == 200
    payload = response.json()
    assistant = payload["assistant_message"]
    assert assistant["safety_status"] == "degraded"
    assert assistant["error_code"] == "BAILIAN_NOT_CONFIGURED"
    assert "secret-token" not in response.text
    assert "api_key=" not in response.text

    with session_factory() as db:
        messages = list(db.scalars(select(ChatMessage).order_by(ChatMessage.id.asc())))
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[1].error_code == "BAILIAN_NOT_CONFIGURED"
        assert "secret-token" not in (messages[1].error_message or "")


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
    Base.metadata.drop_all(bind=engine)


class StubBailianClient:
    model_name = "qwen3.6-plus"

    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[dict[str, str]] = []
        self.json_mode = False

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        json_mode: bool = False,
    ) -> BailianChatCompletion:
        self.messages = messages
        self.json_mode = json_mode
        return BailianChatCompletion(content=self.content, model="qwen3.6-plus", usage={"total_tokens": 88})


class ErrorBailianClient:
    model_name = "qwen3.6-plus"

    async def chat(self, *args: object, **kwargs: object) -> BailianChatCompletion:
        raise BailianConfigurationError("Bailian API key api_key=secret-token is not configured.")


def _create_session(client: TestClient, graph: dict[str, int]) -> int:
    response = client.post(
        "/api/chat/sessions",
        json={
            "current_page": "reports/detail",
            "report_id": graph["report_id"],
            "product_id": graph["product_id"],
            "page_context": {"route": f"/reports/{graph['report_id']}"},
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _seed_chat_graph(session_factory: sessionmaker[Session], *, report_suffix: str = "") -> dict[str, int]:
    with session_factory() as db:
        company = Company(
            name="Q49 Export Co",
            region="Jiangsu",
            industry="Home textile",
            description="A Jiangsu exporter with a source gap note and no secret-token in prompts.",
            target_countries=["US", "JP"],
        )
        db.add(company)
        db.flush()
        product = Product(
            company_id=company.id,
            product_name_cn="Q49测试毯",
            product_name_en="Q49 Throw Blanket",
            category="Home textile",
            cost_price_cny=Decimal("42.00"),
            weight_kg=Decimal("0.900"),
            material="Cotton blend",
            certification="OEKO-TEX",
            moq=120,
            description="Soft throw blanket for export testing.",
        )
        db.add(product)
        db.flush()
        analysis = AnalysisRun(
            company_id=company.id,
            status="fallback_used",
            input_products=[
                {
                    "id": product.id,
                    "product_name_cn": product.product_name_cn,
                    "product_name_en": product.product_name_en,
                    "category": product.category,
                }
            ],
            target_countries=["US"],
            step_logs=[
                {
                    "step_id": "03_data_collection",
                    "title": "Data collection",
                    "status": "fallback_used",
                    "fallback_used": True,
                    "sources": [
                        {
                            "provider": "etsy",
                            "source_label": "CSV fallback",
                            "source_type": "csv_fallback",
                            "fallback_used": True,
                            "detail": "source gap; url=https://example.com/?token=secret-token",
                        }
                    ],
                }
            ],
            workflow_state={
                "provider_sources": [
                    {
                        "provider": "worldbank",
                        "source_label": "World Bank API",
                        "source_type": "api",
                        "fallback_used": False,
                        "api_invoked": True,
                        "detail": "Macro data source gap check.",
                    }
                ],
                "content_trends": [
                    {
                        "product_id": product.id,
                        "country": "US",
                        "keyword": "throw blanket",
                        "content_themes": ["giftable home decor"],
                        "source_item_count": 6,
                    }
                ],
            },
        )
        db.add(analysis)
        db.flush()
        db.add(
            OpportunityScore(
                analysis_id=analysis.id,
                product_id=product.id,
                country="US",
                trend_score=Decimal("81.00"),
                price_score=Decimal("77.00"),
                market_score=Decimal("84.00"),
                supply_score=Decimal("88.00"),
                logistics_score=Decimal("72.00"),
                content_score=Decimal("69.00"),
                total_score=Decimal("82.50"),
                rank=1,
                reason="Structured signals support a cautious entry test.",
                risk="Validate certification and price band before launch.",
                next_action="Run a small localized listing test with conservative claims.",
                fallback_used=True,
                sources=[
                    {
                        "provider": "etsy",
                        "source_label": "CSV fallback",
                        "source_type": "csv_fallback",
                        "fallback_used": True,
                    }
                ],
                evidence={"keyword": "throw blanket", "content_fallback_used": True},
                competitor_analysis={
                    "keyword": "throw blanket",
                    "competition_level": "medium",
                    "price_suggestion": "Use USD 18-24 for an entry test band.",
                },
            )
        )
        db.flush()
        report = report_service.create_report(
            db,
            ReportCreate(
                analysis_id=analysis.id,
                company_id=company.id,
                title="Q49 Report",
                content_markdown=(
                    "# Q49 Report\n\n"
                    "## Recommendation\nUS is the first test market based on directional scores.\n\n"
                    "## Risk\nCertification and price band need manual review.\n\n"
                    f"{report_suffix}"
                ),
                content_html="<article>Q49 Report</article>",
            ),
        )
        return {
            "company_id": company.id,
            "product_id": product.id,
            "analysis_id": analysis.id,
            "report_id": report.id,
        }


def _seed_other_product(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        company = Company(name="Other Co", region="Jiangsu", industry="Other")
        db.add(company)
        db.flush()
        product = Product(company_id=company.id, product_name_cn="Other Product")
        db.add(product)
        db.commit()
        return product.id
