from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "report_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_reports_current_version_id_report_versions",
        ),
        nullable=True,
        index=True,
    )

    analysis_run: Mapped["AnalysisRun"] = relationship("AnalysisRun", back_populates="reports")
    company: Mapped["Company"] = relationship("Company", back_populates="reports")
    versions: Mapped[list["ReportVersion"]] = relationship(
        "ReportVersion",
        back_populates="report",
        cascade="all, delete-orphan",
        foreign_keys="ReportVersion.report_id",
    )
    current_version: Mapped["ReportVersion | None"] = relationship(
        "ReportVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    edit_proposals: Mapped[list["ReportEditProposal"]] = relationship(
        "ReportEditProposal",
        back_populates="report",
        cascade="all, delete-orphan",
        foreign_keys="ReportEditProposal.report_id",
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship("ChatSession", back_populates="report")


class ReportVersion(CreatedAtMixin, Base):
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_id_version_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="generated", index=True)
    source_proposal_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[Report] = relationship(
        "Report",
        back_populates="versions",
        foreign_keys=[report_id],
    )
    parent_version: Mapped["ReportVersion | None"] = relationship(
        "ReportVersion",
        remote_side=[id],
        foreign_keys=[parent_version_id],
    )
    target_edit_proposals: Mapped[list["ReportEditProposal"]] = relationship(
        "ReportEditProposal",
        back_populates="target_version",
        foreign_keys="ReportEditProposal.target_version_id",
    )
    accepted_edit_proposals: Mapped[list["ReportEditProposal"]] = relationship(
        "ReportEditProposal",
        back_populates="accepted_version",
        foreign_keys="ReportEditProposal.accepted_version_id",
    )


class ReportEditProposal(TimestampMixin, Base):
    __tablename__ = "report_edit_proposals"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="confidence_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_chat_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_intent: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    replacement_blocks: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    risk_notes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    accepted_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("report_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped[Report] = relationship(
        "Report",
        back_populates="edit_proposals",
        foreign_keys=[report_id],
    )
    target_version: Mapped[ReportVersion | None] = relationship(
        "ReportVersion",
        back_populates="target_edit_proposals",
        foreign_keys=[target_version_id],
    )
    accepted_version: Mapped[ReportVersion | None] = relationship(
        "ReportVersion",
        back_populates="accepted_edit_proposals",
        foreign_keys=[accepted_version_id],
    )
    source_chat_session: Mapped["ChatSession | None"] = relationship("ChatSession")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="report_edit_proposal",
    )

