"""Safeguards for outbound Gmail — who we are allowed to email."""

from __future__ import annotations

import re

from app.db.google_accounts import list_accounts
from app.google.oauth import _run_async

# Set True when you want outbound email (recap + agent send_email) to work again.
OUTBOUND_EMAIL_ENABLED = True

# When True, recipients must match a connected Google account email exactly.
ONLY_CONNECTED_ACCOUNT_RECIPIENTS = True


def _normalize_email(address: str) -> str:
    """Extract bare email from 'Name <user@example.com>' or plain address."""
    address = address.strip()
    match = re.search(r"<([^>]+)>", address)
    if match:
        return match.group(1).lower().strip()
    return address.lower().strip()


def _parse_recipient_list(recipients: str) -> list[str]:
    if not recipients.strip():
        return []
    return [_normalize_email(part) for part in recipients.split(",") if part.strip()]


def get_connected_account_emails() -> list[str]:
    accounts = _run_async(list_accounts())
    return [account.email.lower() for account in accounts]


def validate_outbound_email(
    *,
    to: str,
    cc: str = "",
    allowed_extra_recipients: set[str] | None = None,
) -> tuple[bool, str]:
    """
    Return (allowed, error_message).

    Blocks all outbound email when OUTBOUND_EMAIL_ENABLED is False.
    When ONLY_CONNECTED_ACCOUNT_RECIPIENTS is True, every To/CC address must be
    one of the user's connected Google account emails (self-only), unless the
    address appears in allowed_extra_recipients (e.g. thread participants for replies).
    """
    if not OUTBOUND_EMAIL_ENABLED:
        return False, "Outbound email is temporarily disabled."

    recipients = _parse_recipient_list(to) + _parse_recipient_list(cc)
    if not recipients:
        return False, "At least one recipient is required."

    if not ONLY_CONNECTED_ACCOUNT_RECIPIENTS:
        return True, ""

    allowed = set(get_connected_account_emails())
    if allowed_extra_recipients:
        allowed |= {_normalize_email(email) for email in allowed_extra_recipients}
    if not allowed:
        return False, "No connected Google accounts found."

    blocked = [r for r in recipients if r not in allowed]
    if blocked:
        allowed_list = ", ".join(sorted(allowed))
        return (
            False,
            "Email can only be sent to your connected account(s): "
            f"{allowed_list}. Blocked: {', '.join(blocked)}",
        )

    return True, ""
