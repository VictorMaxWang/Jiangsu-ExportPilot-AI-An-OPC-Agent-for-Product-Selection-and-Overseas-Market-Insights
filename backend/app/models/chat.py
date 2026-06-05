from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_page: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    context_refs: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    safety_status: Mapped[str] = mapped_column(String(32), nullable=False, default="safe", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped["Company | None"] = relationship("Company")
    product: Mapped["Product | None"] = relationship("Product")
    analysis_run: Mapped["AnalysisRun | None"] = relationship("AnalysisRun")
    report: Mapped["Report | None"] = relationship("Report", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessage(CreatedAtMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    context_refs: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    safety_status: Mapped[str] = mapped_column(String(32), nullable=False, default="safe", index=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_edit_proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_edit_proposals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")
    report_edit_proposal: Mapped["ReportEditProposal | None"] = relationship(
        "ReportEditProposal",
        back_populates="chat_messages",
    )
