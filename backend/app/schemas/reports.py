from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    created_at: datetime
    updated_at: datetime


class ReportListItem(ReportRead):
    pass
