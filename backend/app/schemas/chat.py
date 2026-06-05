from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.reports import ReportEditProposalRead


ChatRole = Literal["user", "assistant", "system"]


class ChatSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    current_page: str | None = Field(default=None, max_length=128)
    company_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    analysis_id: int | None = Field(default=None, ge=1)
    report_id: int | None = Field(default=None, ge=1)
    context_refs: dict[str, Any] | None = None
    page_context: dict[str, Any] | None = None

    @field_validator("title", "current_page", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    current_page: str | None = None
    company_id: int | None = None
    product_id: int | None = None
    analysis_id: int | None = None
    report_id: int | None = None
    context_refs: dict[str, Any] | None = None
    page_context: dict[str, Any] | None = None
    safety_status: str
    status: str
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionRead] = Field(default_factory=list)
    total: int = Field(ge=0)


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    content: str = Field(min_length=1, max_length=8000)
    context_refs: dict[str, Any] | None = None
    current_page: str | None = Field(default=None, max_length=128)
    company_id: int | None = Field(default=None, ge=1)
    product_id: int | None = Field(default=None, ge=1)
    analysis_id: int | None = Field(default=None, ge=1)
    report_id: int | None = Field(default=None, ge=1)
    page_context: dict[str, Any] | None = None

    @field_validator("content", mode="before")
    @classmethod
    def _clean_content(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("content is required")
        return text

    @field_validator("current_page", mode="before")
    @classmethod
    def _clean_current_page(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    content_redacted: bool
    context_refs: dict[str, Any] | None = None
    safety_status: str
    model_used: str | None = None
    token_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    report_edit_proposal_id: int | None = None
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageRead] = Field(default_factory=list)
    total: int = Field(ge=0)


class ChatMessageSendResponse(BaseModel):
    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    proposal: ReportEditProposalRead | None = None
