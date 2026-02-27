"""Exceptions for source search failures."""

from __future__ import annotations


class SourceSearchError(RuntimeError):
    """Raised when a source search request fails with a non-timeout error."""

    def __init__(
        self,
        platform: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        detail = f"{platform} search failed: {message}"
        if status_code is not None:
            detail = f"{detail} (status={status_code})"
        super().__init__(detail)
        self.platform = platform
        self.status_code = status_code
