"""Authentication models.

认证相关的数据模型。
"""

from __future__ import annotations

from pydantic import Field

from ideago.models.base import BaseModel


class AuthUser(BaseModel):
    """Authenticated user extracted from a verified Supabase JWT."""

    id: str = Field(description="Supabase user UUID")
    email: str = Field(default="", description="User email address")
    role: str = Field(default="user", description="User role: 'user' or 'admin'")
    provider: str = Field(default="", description="Auth provider")
    session_id: str = Field(default="", description="Backend-managed custom session id")
