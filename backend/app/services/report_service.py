from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Report, ReportEditProposal, ReportVersion
from app.schemas import ReportCreate, ReportUpdate
from app.services.report_quality import assess_report_markdown, quality_issue_messages, report_fallback_expected


class ReportVersioningError(ValueError):
    def __init__(self, code: str, message: str, *, quality: dict[str, Any] | None = None) -> None:
        self.code = code
        self.quality = quality
        super().__init__(message)


def count_reports(db: Session, *, analysis_id: int | None = None) -> int:
    statement = select(func.count()).select_from(Report)
    if analysis_id is not None:
        statement = statement.where(Report.analysis_id == analysis_id)
    return db.scalar(statement) or 0


def list_reports(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    *,
    analysis_id: int | None = None,
) -> list[Report]:
    statement = select(Report)
    if analysis_id is not None:
        statement = statement.where(Report.analysis_id == analysis_id)
    statement = statement.order_by(Report.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(statement))


def get_report(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)


def list_report_versions(db: Session, report_id: int) -> list[ReportVersion]:
    return list(
        db.scalars(
            select(ReportVersion)
            .where(ReportVersion.report_id == report_id)
            .order_by(ReportVersion.version_number.desc(), ReportVersion.id.desc())
        )
    )


def get_report_version(db: Session, report_id: int, version_id: int) -> ReportVersion | None:
    version = db.get(ReportVersion, version_id)
    if version is None or version.report_id != report_id:
        return None
    return version


def create_report(db: Session, payload: ReportCreate) -> Report:
    report = Report(**payload.model_dump())
    db.add(report)
    db.flush()
    version = ReportVersion(
        report_id=report.id,
        version_number=1,
        content_markdown=report.content_markdown,
        content_html=report.content_html,
        source_type="generated",
        created_by="system",
        version_note="Initial generated report version.",
    )
    db.add(version)
    db.flush()
    report.current_version_id = version.id
    db.commit()
    db.refresh(report)
    return report


def update_report(db: Session, report: Report, payload: ReportUpdate) -> Report:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.commit()
    db.refresh(report)
    return report


def delete_report(db: Session, report: Report) -> None:
    db.delete(report)
    db.commit()


def confirm_report_edit_proposal(
    db: Session,
    proposal_id: int,
    *,
    actor: str = "user",
    decision_note: str | None = None,
) -> tuple[Report, ReportVersion, ReportEditProposal]:
    proposal = db.get(ReportEditProposal, proposal_id)
    if proposal is None:
        raise ReportVersioningError("REPORT_PROPOSAL_NOT_FOUND", "Report edit proposal not found.")
    report = db.get(Report, proposal.report_id)
    if report is None:
        raise ReportVersioningError("REPORT_NOT_FOUND", "Report not found.")
    if proposal.status == "accepted" and proposal.accepted_version_id is not None:
        accepted = db.get(ReportVersion, proposal.accepted_version_id)
        if accepted is None:
            raise ReportVersioningError("REPORT_VERSION_NOT_FOUND", "Accepted report version not found.")
        if accepted.report_id != report.id:
            raise ReportVersioningError("REPORT_VERSION_MISMATCH", "Accepted report version does not belong to this report.")
        return report, accepted, proposal
    if proposal.status == "rejected":
        raise ReportVersioningError("REPORT_PROPOSAL_REJECTED", "Rejected proposals cannot be applied.")
    if proposal.status not in {"draft", "pending_review"}:
        raise ReportVersioningError("REPORT_PROPOSAL_INVALID_STATUS", "Proposal is not ready to apply.")
    if proposal.target_version_id is not None:
        target = db.get(ReportVersion, proposal.target_version_id)
        if target is None or target.report_id != report.id:
            raise ReportVersioningError("REPORT_VERSION_MISMATCH", "Proposal target version does not belong to this report.")
    if proposal.target_version_id is not None and report.current_version_id != proposal.target_version_id:
        raise ReportVersioningError(
            "REPORT_PROPOSAL_STALE",
            "The report changed after this proposal was created. Ask the assistant to revise the latest version.",
        )
    if not proposal.proposed_markdown:
        quality = _attach_quality(db, proposal, report, proposal.proposed_markdown)
        db.commit()
        raise ReportVersioningError("REPORT_PROPOSAL_EMPTY_DRAFT", "Proposal markdown draft is required.", quality=quality)

    quality = _attach_quality(db, proposal, report, proposal.proposed_markdown)
    if quality.get("status") == "blocked":
        db.commit()
        raise ReportVersioningError(
            "REPORT_QUALITY_BLOCKED",
            "Report quality checks blocked this proposal.",
            quality=quality,
        )

    version = ReportVersion(
        report_id=report.id,
        version_number=_next_version_number(db, report.id),
        parent_version_id=proposal.target_version_id or report.current_version_id,
        content_markdown=proposal.proposed_markdown,
        content_html=_render_html(proposal.proposed_markdown),
        source_type="proposal",
        source_proposal_id=proposal.id,
        created_by=actor,
        version_note=decision_note or _proposal_version_note(proposal),
    )
    db.add(version)
    db.flush()

    proposal.status = "accepted"
    proposal.accepted_version_id = version.id
    report.current_version_id = version.id
    report.content_markdown = version.content_markdown
    report.content_html = version.content_html
    db.commit()
    db.refresh(report)
    db.refresh(version)
    db.refresh(proposal)
    return report, version, proposal


def reject_report_edit_proposal(
    db: Session,
    proposal_id: int,
    *,
    decision_note: str | None = None,
) -> ReportEditProposal:
    proposal = db.get(ReportEditProposal, proposal_id)
    if proposal is None:
        raise ReportVersioningError("REPORT_PROPOSAL_NOT_FOUND", "Report edit proposal not found.")
    if proposal.status == "accepted":
        raise ReportVersioningError("REPORT_PROPOSAL_ACCEPTED", "Accepted proposals cannot be rejected.")
    proposal.status = "rejected"
    if decision_note:
        diff = proposal.diff if isinstance(proposal.diff, dict) else {}
        diff = dict(diff)
        diff["decision_note"] = decision_note
        proposal.diff = diff
    db.commit()
    db.refresh(proposal)
    return proposal


def restore_report_version(
    db: Session,
    report_id: int,
    version_id: int,
    *,
    actor: str = "user",
    decision_note: str | None = None,
) -> tuple[Report, ReportVersion]:
    report = db.get(Report, report_id)
    if report is None:
        raise ReportVersioningError("REPORT_NOT_FOUND", "Report not found.")
    source_version = get_report_version(db, report_id, version_id)
    if source_version is None:
        raise ReportVersioningError("REPORT_VERSION_NOT_FOUND", "Report version not found.")
    if report.current_version_id == source_version.id:
        raise ReportVersioningError("REPORT_VERSION_ALREADY_CURRENT", "This report version is already current.")

    version = ReportVersion(
        report_id=report.id,
        version_number=_next_version_number(db, report.id),
        parent_version_id=report.current_version_id,
        content_markdown=source_version.content_markdown,
        content_html=source_version.content_html or _render_html(source_version.content_markdown or ""),
        source_type="restore",
        source_proposal_id=None,
        created_by=actor,
        version_note=decision_note or f"Restored from report version {source_version.version_number}.",
    )
    db.add(version)
    db.flush()
    report.current_version_id = version.id
    report.content_markdown = version.content_markdown
    report.content_html = version.content_html
    db.commit()
    db.refresh(report)
    db.refresh(version)
    return report, version


def _attach_quality(
    db: Session,
    proposal: ReportEditProposal,
    report: Report,
    markdown: str | None,
) -> dict[str, Any]:
    quality = assess_report_markdown(markdown, fallback_expected=report_fallback_expected(db, report))
    diff = proposal.diff if isinstance(proposal.diff, dict) else {}
    diff = dict(diff)
    diff["quality"] = quality
    proposal.diff = diff
    notes = list(proposal.risk_notes or [])
    for message in quality_issue_messages(quality):
        if message not in notes:
            notes.append(message)
    proposal.risk_notes = notes
    return quality


def _next_version_number(db: Session, report_id: int) -> int:
    value = db.scalar(select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == report_id))
    return int(value or 0) + 1


def _proposal_version_note(proposal: ReportEditProposal) -> str:
    diff = proposal.diff if isinstance(proposal.diff, dict) else {}
    summary = diff.get("summary")
    return str(summary).strip() if isinstance(summary, str) and summary.strip() else "Accepted report edit proposal."


def _render_html(markdown: str) -> str:
    from app.services.reports.report_generator import render_report_html

    return render_report_html(markdown)
