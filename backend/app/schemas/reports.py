from datetime import datetime

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
