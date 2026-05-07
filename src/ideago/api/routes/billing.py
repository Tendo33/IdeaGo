"""Billing endpoints — Stripe checkout, portal, subscription status, webhook."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ideago.api.errors import AppError, ErrorCode
from ideago.auth.dependencies import get_optional_user
from ideago.auth.models import AuthUser
from ideago.billing.stripe_service import (
    construct_webhook_event,
    create_checkout_session,
    create_portal_session,
    get_or_create_customer,
    handle_webhook_event,
    is_configured,
)
from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

router = APIRouter(tags=["billing"])
logger = get_logger(__name__)


def _raise_temporarily_unavailable() -> None:
    """Hide user-facing billing flows until pricing is re-enabled."""
    raise AppError(404, ErrorCode.NOT_FOUND, "Billing is temporarily unavailable")


def _require_user(user: AuthUser | None) -> AuthUser:
    """Keep auth enforcement local so hidden routes still return 404 first."""
    if user is None:
        raise AppError(401, ErrorCode.NOT_AUTHORIZED, "Not authenticated")
    return user


def _validate_redirect_url(url: str, label: str) -> None:
    """Reject redirect URLs that don't match the configured frontend origin."""
    from urllib.parse import urlparse

    settings = get_settings()
    configured = settings.frontend_app_url.strip().rstrip("/")
    if not configured:
        raise AppError(
            500,
            ErrorCode.VALIDATION_ERROR,
            "FRONTEND_APP_URL must be configured for billing redirects",
        )

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise AppError(400, ErrorCode.VALIDATION_ERROR, f"Invalid {label}")

    try:
        allowed = urlparse(configured)
    except ValueError:
        return

    if parsed.scheme != allowed.scheme or parsed.netloc != allowed.netloc:
        raise AppError(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"{label} must point to {allowed.scheme}://{allowed.netloc}",
        )


class CheckoutRequest(BaseModel):
    success_url: str = Field(
        ..., max_length=2000, description="URL to redirect after successful payment"
    )
    cancel_url: str = Field(
        ..., max_length=2000, description="URL to redirect if user cancels"
    )


class CheckoutResponse(BaseModel):
    url: str


class PortalRequest(BaseModel):
    return_url: str = Field(
        ..., max_length=2000, description="URL to return to after portal session"
    )


class PortalResponse(BaseModel):
    url: str


class SubscriptionStatus(BaseModel):
    plan: str
    has_subscription: bool
    stripe_configured: bool


@router.post(
    "/billing/checkout",
    response_model=CheckoutResponse,
    include_in_schema=False,
)
async def create_checkout(
    body: CheckoutRequest,
    user: AuthUser | None = Depends(get_optional_user),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for upgrading to Pro."""
    _raise_temporarily_unavailable()
    user = _require_user(user)
    if not is_configured():
        raise AppError(503, ErrorCode.BILLING_NOT_CONFIGURED, "Billing not configured")

    settings = get_settings()
    if not settings.stripe_pro_price_id:
        raise AppError(503, ErrorCode.BILLING_NO_PRICE, "No Pro price configured")

    _validate_redirect_url(body.success_url, "success_url")
    _validate_redirect_url(body.cancel_url, "cancel_url")

    try:
        customer_id = await get_or_create_customer(user.id, user.email)
        url = await create_checkout_session(
            customer_id=customer_id,
            price_id=settings.stripe_pro_price_id,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
        if not url:
            raise AppError(
                502,
                ErrorCode.BILLING_CHECKOUT_FAILED,
                "Failed to create checkout session",
            )
        return CheckoutResponse(url=url)
    except AppError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Checkout session creation failed")
        raise AppError(
            500, ErrorCode.BILLING_CHECKOUT_FAILED, "Failed to create checkout session"
        ) from exc


@router.post(
    "/billing/portal",
    response_model=PortalResponse,
    include_in_schema=False,
)
async def create_portal(
    body: PortalRequest,
    user: AuthUser | None = Depends(get_optional_user),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for managing subscription."""
    _raise_temporarily_unavailable()
    user = _require_user(user)
    if not is_configured():
        raise AppError(503, ErrorCode.BILLING_NOT_CONFIGURED, "Billing not configured")

    _validate_redirect_url(body.return_url, "return_url")

    try:
        customer_id = await get_or_create_customer(user.id, user.email)
        url = await create_portal_session(
            customer_id=customer_id,
            return_url=body.return_url,
        )
        return PortalResponse(url=url)
    except AppError:
        raise
    except Exception as exc:
        logger.opt(exception=True).error("Portal session creation failed")
        raise AppError(
            500, ErrorCode.BILLING_PORTAL_FAILED, "Failed to create portal session"
        ) from exc


@router.get(
    "/billing/status",
    response_model=SubscriptionStatus,
    include_in_schema=False,
)
async def get_subscription_status(
    user: AuthUser | None = Depends(get_optional_user),
) -> SubscriptionStatus:
    """Return the user's current plan and subscription status."""
    _raise_temporarily_unavailable()
    user = _require_user(user)
    from ideago.auth.supabase_admin import get_quota_info

    quota = await get_quota_info(user.id)
    plan = quota.get("plan", "free")

    return SubscriptionStatus(
        plan=plan,
        has_subscription=plan != "free",
        stripe_configured=is_configured(),
    )


@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict:
    """Stripe webhook endpoint. Verifies signature and processes events."""
    if not is_configured():
        raise AppError(503, ErrorCode.BILLING_NOT_CONFIGURED, "Billing not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except Exception as exc:
        logger.opt(exception=True).warning(
            "Stripe webhook signature verification failed"
        )
        raise AppError(
            400, ErrorCode.BILLING_INVALID_SIGNATURE, "Invalid signature"
        ) from exc

    try:
        await handle_webhook_event(event)
    except Exception as exc:
        logger.opt(exception=True).error("Webhook event processing failed")
        raise AppError(
            500, ErrorCode.INTERNAL_ERROR, "Webhook event processing failed"
        ) from exc

    return {"received": True}
