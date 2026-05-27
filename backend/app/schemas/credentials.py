from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiCredentialBase(BaseModel):
    provider: str
    key_name: str
    enabled: bool = True
    last_test_status: str | None = None
    last_test_at: datetime | None = None


class ApiCredentialCreate(ApiCredentialBase):
    encrypted_value: str


class ApiCredentialUpdate(BaseModel):
    provider: str | None = None
    key_name: str | None = None
    encrypted_value: str | None = None
    enabled: bool | None = None
    last_test_status: str | None = None
    last_test_at: datetime | None = None


class ApiCredentialRead(ApiCredentialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ApiCredentialListItem(ApiCredentialRead):
    pass
