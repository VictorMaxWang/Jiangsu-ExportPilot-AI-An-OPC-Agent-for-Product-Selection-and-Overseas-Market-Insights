from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ImportMode = Literal["insert", "validate"]


class CsvImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str | None = None
    mode: ImportMode = "insert"
    company_id: int | None = Field(default=None, ge=1)


class CsvImportErrorDetail(BaseModel):
    row_number: int | None = None
    field: str | None = None
    message: str
    raw_value: str | None = None


class CsvImportResult(BaseModel):
    dataset: str
    file_name: str
    mode: ImportMode
    source: str = "csv_fallback"
    total_rows: int
    valid_rows: int
    inserted: int
    failed: int
    errors: list[CsvImportErrorDetail] = Field(default_factory=list)
