from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportColumn(BaseModel):
    key: str
    label: str


class ReportResult(BaseModel):
    report_key: str
    title: str
    columns: list[ReportColumn]
    rows: list[dict[str, Any]]
    summary: dict[str, Any] = Field(default_factory=dict)
    total_count: int = 0
    generated_at: datetime
    truncated: bool = False
