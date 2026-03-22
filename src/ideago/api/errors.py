"""Structured error codes and application error class.

Provides machine-parseable error responses in the format:
    {"error": {"code": "REPORT_NOT_FOUND", "message": "Report not found"}}
"""

from __future__ import annotations

from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    """Machine-readable error codes returned in API error responses."""

    REPORT_NOT_FOUND = "REPORT_NOT_FOUND"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    ANALYSIS_NOT_FOUND = "ANALYSIS_NOT_FOUND"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BILLING_NOT_CONFIGURED = "BILLING_NOT_CONFIGURED"
    BILLING_NO_PRICE = "BILLING_NO_PRICE"
    BILLING_CHECKOUT_FAILED = "BILLING_CHECKOUT_FAILED"
    BILLING_PORTAL_FAILED = "BILLING_PORTAL_FAILED"
    BILLING_INVALID_SIGNATURE = "BILLING_INVALID_SIGNATURE"
    CSRF_MISSING_HEADER = "CSRF_MISSING_HEADER"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_NOT_CONFIGURED = "AUTH_NOT_CONFIGURED"
    AUTH_FAILED = "AUTH_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(HTTPException):
    """Application error with a structured error code.

    Extends HTTPException so existing FastAPI exception handlers catch it,
    and a custom handler can format the ``detail`` dict consistently.
    """

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code.value, "message": message},
        )
        self.code = code
