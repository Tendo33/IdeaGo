"""API request/response schemas.

API 请求/响应模型。
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator

from ideago.models.base import BaseModel


class AnalyzeRequest(BaseModel):
    """Request body for the analyze endpoint."""

    query: str = Field(
        min_length=5,
        max_length=1000,
        description="Natural language startup idea description",
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Collapse whitespace and reject garbage input."""
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 5:
            raise ValueError("Query too short after whitespace normalization")
        alpha_count = sum(1 for c in v if c.isalpha())
        if len(v) > 0 and alpha_count / len(v) < 0.4:
            raise ValueError("Query must contain mostly alphabetic characters")
        return v


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint."""

    report_id: str = Field(description="Unique ID for the report")


class ReportStatusResponse(BaseModel):
    """Status check response for a report."""

    report_id: str
    status: str = Field(description="processing | completed | error | not_found")


class ReportListItem(BaseModel):
    """Summary item for the reports list endpoint."""

    id: str
    query: str
    created_at: datetime
    competitor_count: int = 0


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str = ""
