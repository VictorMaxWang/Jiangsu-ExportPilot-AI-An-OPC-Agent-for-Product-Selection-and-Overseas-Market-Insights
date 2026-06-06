from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportBase(BaseModel):
    analysis_id: int
    company_id: int
    title: str
    content_markdown: str | None = None
    content_html: str | None = None
    pdf_url: str | None = None


class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseModel):
    analysis_id: int | None = None
    company_id: int | None = None
    title: str | None = None
    content_markdown: str | None = None
    content_html: str | None = None
    pdf_url: str | None = None


class ReportRead(ReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    current_version_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ReportListItem(ReportRead):
    pass


class ReportListResponse(BaseModel):
    items: list[ReportListItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReportGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: int = Field(ge=1)
    force_regenerate: bool = False


class ReportVersionBase(BaseModel):
    report_id: int = Field(ge=1)
    version_number: int = Field(ge=1)
    parent_version_id: int | None = Field(default=None, ge=1)
    content_markdown: str | None = None
    content_html: str | None = None
    source_type: str = Field(default="generated", max_length=32)
    source_proposal_id: int | None = Field(default=None, ge=1)
    created_by: str | None = Field(default=None, max_length=128)
    version_note: str | None = None


class ReportVersionCreate(ReportVersionBase):
    pass


class ReportVersionRead(ReportVersionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ReportVersionListResponse(BaseModel):
    items: list[ReportVersionRead] = Field(default_factory=list)
    total: int = Field(ge=0)
    current_version_id: int | None = None


class ReportEditProposalBase(BaseModel):
    report_id: int = Field(ge=1)
    target_version_id: int | None = Field(default=None, ge=1)
    source_chat_session_id: int | None = Field(default=None, ge=1)
    user_intent: str = Field(min_length=1)
    proposed_markdown: str | None = None
    proposed_html: str | None = None
    diff: dict[str, Any] | None = None
    replacement_blocks: list[dict[str, Any]] | None = None
    risk_notes: list[str] | None = None
    evidence: list[dict[str, Any]] | None = None
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)
    status: str = Field(default="draft", max_length=32)
    accepted_version_id: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class ReportEditProposalCreate(ReportEditProposalBase):
    pass


class ReportEditProposalRead(ReportEditProposalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ReportProposalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class ReportVersionRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class ReportProposalConfirmResponse(BaseModel):
    report: ReportRead
    version: ReportVersionRead
    proposal: ReportEditProposalRead


class ReportVersionRestoreResponse(BaseModel):
    report: ReportRead
    version: ReportVersionRead
