"""Public runtime configuration endpoint.

The browser bundle used to receive Supabase / Turnstile / Sentry values as
Vite build-time constants (``VITE_*``). That made every published Docker image
carry whatever configuration the build machine happened to have — and the
release workflow passed none, so published images shipped an unusable login.

This endpoint moves those values to runtime. The frontend fetches it once
before mounting, so one image works for any deployment.

Only values that are *already* public by design are exposed here. Everything
is listed explicitly: never serialize ``Settings`` wholesale, or a future
secret-valued field would silently leak to every browser.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ideago.config.settings import get_settings

router = APIRouter(tags=["config"])

# Browsers may reuse this briefly; it changes only on redeploy.
_CACHE_CONTROL = "public, max-age=60"


class PublicConfig(BaseModel):
    """Configuration the browser is allowed to see.

    Adding a field here makes it world-readable. Secrets such as
    ``SUPABASE_SERVICE_ROLE_KEY``, ``AUTH_SESSION_SECRET``,
    ``TURNSTILE_SECRET_KEY``, ``STRIPE_SECRET_KEY`` and ``OPENAI_API_KEY``
    must never appear.
    """

    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_anon_key: str = Field(
        default="", description="Supabase anon/publishable key"
    )
    turnstile_site_key: str = Field(
        default="", description="Cloudflare Turnstile site key"
    )
    sentry_dsn: str = Field(default="", description="Browser Sentry DSN")
    pricing_enabled: bool = Field(
        default=False, description="Whether the SPA exposes pricing discovery"
    )
    environment: str = Field(default="development", description="Runtime environment")


def build_public_config() -> PublicConfig:
    """Assemble the public config from settings using an explicit allowlist."""
    settings = get_settings()
    return PublicConfig(
        supabase_url=settings.supabase_url.strip(),
        supabase_anon_key=settings.supabase_anon_key.strip(),
        turnstile_site_key=settings.turnstile_site_key.strip(),
        sentry_dsn=settings.frontend_sentry_dsn.strip(),
        pricing_enabled=settings.pricing_enabled,
        environment=settings.environment,
    )


@router.get("/config", response_model=PublicConfig)
async def get_public_config(response: Response) -> PublicConfig:
    """Return public frontend configuration.

    Unauthenticated on purpose: every value here already ships to the browser.
    """
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return build_public_config()
