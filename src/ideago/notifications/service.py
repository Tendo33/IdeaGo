"""Notification service abstraction.

Provides a protocol for sending notifications with a log-only default
implementation. To enable real email delivery, swap in an SMTP or
transactional-email implementation (e.g. Resend, SendGrid) and configure
the relevant environment variables.
"""

from __future__ import annotations

from typing import Protocol

from ideago.observability.log_config import get_logger

logger = get_logger(__name__)


class NotificationSender(Protocol):
    """Protocol for outbound notifications."""

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str = "",
    ) -> bool:
        """Send a notification. Returns True on success."""
        _ = body_text, body_html
        raise NotImplementedError


class LogNotificationSender:
    """Logs notifications instead of sending them.

    Used as a safe default when no email service is configured. Replace
    with a real implementation by setting ``NOTIFICATION_PROVIDER`` in
    the environment.
    """

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str = "",
    ) -> bool:
        logger.info(
            "Notification (log-only) to={} subject={} text_length={} has_html={}",
            to,
            subject,
            len(body_text),
            bool(body_html),
        )
        return True


_sender: NotificationSender | None = None


def get_notification_sender() -> NotificationSender:
    global _sender
    if _sender is None:
        _sender = LogNotificationSender()
    return _sender


async def notify_welcome(email: str, display_name: str) -> bool:
    """Send a welcome email to a new user."""
    sender = get_notification_sender()
    return await sender.send(
        to=email,
        subject="Welcome to IdeaGo!",
        body_text=f"Hi {display_name},\n\nWelcome to IdeaGo. Start by describing your startup idea.",
    )


async def notify_quota_warning(email: str, usage: int, limit: int) -> bool:
    """Warn a user approaching their quota limit."""
    sender = get_notification_sender()
    return await sender.send(
        to=email,
        subject="IdeaGo: You're approaching your analysis limit",
        body_text=(
            f"You've used {usage} of {limit} analyses today. "
            "Come back after your daily reset or upgrade for more."
        ),
    )


async def notify_report_ready(email: str, report_id: str, query: str) -> bool:
    """Notify a user that their report is ready."""
    sender = get_notification_sender()
    return await sender.send(
        to=email,
        subject=f"Your IdeaGo report is ready: {query[:60]}",
        body_text=f'Your analysis for "{query}" is complete.\n\nReport ID: {report_id}',
    )
