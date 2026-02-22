"""Example models exposed by the public package API."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import Field, field_validator

from .base import BaseModel, TimestampMixin

T = TypeVar("T")


class User(TimestampMixin):
    """Example user model."""

    id: int = Field(..., ge=1, description="User id")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    full_name: str = Field(default="", description="Display name")
    is_active: bool = Field(default=True, description="Active flag")

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.replace("_", "").isalnum():
            raise ValueError("Username must be alphanumeric with underscores")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Invalid email format")
        return value


class ApiResponse(BaseModel, Generic[T]):
    """Generic API response model."""

    success: bool = Field(..., description="Whether request was successful")
    data: T | None = Field(default=None, description="Response payload")
    message: str = Field(default="", description="Response message")
    error_code: str | None = Field(default=None, description="Optional error code")


class PaginatedResponse(ApiResponse[list[T]], Generic[T]):
    """Generic paginated API response model."""

    page: int = Field(default=1, ge=1, description="Current page")
    page_size: int = Field(default=20, ge=1, description="Page size")
    total: int = Field(default=0, ge=0, description="Total items")


class ConfigModel(BaseModel):
    """Example configuration model."""

    key: str = Field(..., min_length=1, description="Configuration key")
    value: str = Field(default="", description="Configuration value")
    description: str = Field(default="", description="Configuration description")
