from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyBase(BaseModel):
    name: str
    region: str | None = None
    industry: str | None = None
    description: str | None = None
    target_countries: list[str] | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    industry: str | None = None
    description: str | None = None
    target_countries: list[str] | None = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CompanyListItem(CompanyRead):
    pass


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    total: int
