"""Stripe billing service — checkout, portal, webhook processing.

Wraps the Stripe SDK for creating checkout sessions, customer portal
sessions, and processing webhook events to keep profiles in sync.
"""

from __future__ import annotations

import asyncio
from functools import partial

import stripe

from ideago.config.settings import get_settings
from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


def _configure() -> bool:
    """Lazily configure Stripe API key. Returns True if configured."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return False
    stripe.api_key = settings.stripe_secret_key
    return True


def is_configured() -> bool:
    return bool(get_settings().stripe_secret_key)


async def get_or_create_customer(user_id: str, email: str) -> str:
    """Return existing Stripe customer ID or create a new one.

    Checks profiles table first; creates in Stripe if missing.
    """
    _configure()
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase not configured")

    import httpx

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers=headers,
            params={
                "id": f"eq.{user_id}",
                "select": "stripe_customer_id",
                "limit": "1",
            },
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows and rows[0].get("stripe_customer_id"):
                return rows[0]["stripe_customer_id"]

        loop = asyncio.get_running_loop()
        customer = await loop.run_in_executor(
            None,
            partial(stripe.Customer.create, email=email, metadata={"user_id": user_id}),
        )

        patch_resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            headers={**headers, "Prefer": "return=minimal"},
            params={"id": f"eq.{user_id}"},
            json={"stripe_customer_id": customer.id},
        )
        if patch_resp.status_code not in (200, 204):
            logger.warning(
                "Failed to save stripe_customer_id for user {}: {}",
                user_id,
                patch_resp.status_code,
            )

    return customer.id


async def create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return its URL."""
    _configure()
    loop = asyncio.get_running_loop()
    session = await loop.run_in_executor(
        None,
        partial(
            stripe.checkout.Session.create,
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
        ),
    )
    return session.url or ""


async def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session and return its URL."""
    _configure()
    loop = asyncio.get_running_loop()
    session = await loop.run_in_executor(
        None,
        partial(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        ),
    )
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and construct a Stripe webhook event."""
    settings = get_settings()
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )


async def _try_claim_event(event_id: str, event_type: str) -> bool:
    """Atomically claim a Stripe event for processing (insert-first idempotency).

    Returns True if this call successfully claimed the event (i.e. the row
    was inserted). Returns False if the event was already claimed by another
    worker or if Supabase is not configured.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return True

    import httpx

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=representation",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{settings.supabase_url}/rest/v1/processed_webhook_events",
                headers=headers,
                json={"event_id": event_id, "event_type": event_type},
            )
            if resp.status_code == 409:
                return False
            if resp.status_code in (200, 201):
                rows = resp.json()
                return not (isinstance(rows, list) and len(rows) == 0)
            return True
    except Exception:
        logger.opt(exception=True).debug("Idempotency claim failed, proceeding anyway")
        return True


async def handle_webhook_event(event: stripe.Event) -> None:
    """Process a verified Stripe webhook event.

    Uses insert-first idempotency: claims the event atomically before
    processing. If a concurrent worker already claimed it, this call
    returns early.
    """
    if not await _try_claim_event(event.id, event.type):
        logger.debug("Skipping already-claimed Stripe event {}", event.id)
        return

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase not configured; skipping webhook processing")
        return

    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    event_type = event.type
    data_object = event.data.object

    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        if event_type == "checkout.session.completed":
            customer_id = data_object.get("customer", "")
            subscription_id = data_object.get("subscription", "")
            if customer_id and subscription_id:
                await client.patch(
                    f"{settings.supabase_url}/rest/v1/profiles",
                    headers=headers,
                    params={"stripe_customer_id": f"eq.{customer_id}"},
                    json={
                        "plan": "pro",
                        "stripe_subscription_id": subscription_id,
                    },
                )
                logger.info(
                    "Checkout completed: customer={} subscription={}",
                    customer_id,
                    subscription_id,
                )

        elif event_type in (
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            subscription = data_object
            customer_id = subscription.get("customer", "")
            status = subscription.get("status", "")

            plan = "pro" if status in ("active", "trialing") else "free"

            update_body: dict[str, str | None] = {"plan": plan}
            if status in ("canceled", "unpaid", "incomplete_expired"):
                update_body["stripe_subscription_id"] = None

            if customer_id:
                await client.patch(
                    f"{settings.supabase_url}/rest/v1/profiles",
                    headers=headers,
                    params={"stripe_customer_id": f"eq.{customer_id}"},
                    json=update_body,
                )
                logger.info(
                    "Subscription {}: customer={} status={} -> plan={}",
                    event_type.split(".")[-1],
                    customer_id,
                    status,
                    plan,
                )
        else:
            logger.debug("Unhandled Stripe event: {}", event_type)
