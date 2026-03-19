"""Auth endpoints — current user info.

认证端点：获取当前登录用户信息。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user."""
    return {"id": user.id, "email": user.email}
