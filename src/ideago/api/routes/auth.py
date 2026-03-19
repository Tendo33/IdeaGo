"""Auth endpoints — current user info and quota.

认证端点：获取当前登录用户信息及用量配额。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ideago.auth.dependencies import get_current_user
from ideago.auth.models import AuthUser
from ideago.auth.supabase_admin import get_quota_info

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user."""
    return {"id": user.id, "email": user.email}


@router.get("/auth/quota")
async def get_user_quota(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the user's current usage quota information."""
    return await get_quota_info(user.id)
