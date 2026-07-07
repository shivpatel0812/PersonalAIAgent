"""Orchestrates the scheduled email recap agent."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

import pytz

from app.agents.email_recap import settings as recap_settings
from app.agents.email_recap.gmail import list_recap_candidates, send_html_recap_email
from app.agents.email_recap.intelligent_summarizer import generate_intelligent_recap_html
from app.ai.config import settings as ai_settings
from app.db.google_accounts import get_primary_account, list_accounts
from app.google.oauth import load_credentials

logger = logging.getLogger(__name__)

RecapSlot = Literal["morning", "noon", "evening", "night"]

LOOKBACK_HOURS = {
    "morning": 10,  # overnight since ~11 PM
    "noon": 4,      # since 9 AM
    "evening": 6,   # since noon
    "night": 7,     # since 5 PM
}

SLOT_LABELS = {
    "morning": "Morning",
    "noon": "Midday",
    "evening": "Evening",
    "night": "Night",
}


async def run_email_recap(slot: RecapSlot = "morning") -> dict:
    """
    Scan connected Google accounts and email a recap of important messages.

    Args:
        slot: "morning" (7am) or "evening" (5pm) — affects lookback window and subject line.
    """
    if not recap_settings.ENABLED:
        return {"status": "skipped", "reason": "email recap disabled"}

    if not ai_settings.openai_configured:
        return {"status": "skipped", "reason": "OpenAI not configured"}

    accounts = await list_accounts()
    if not accounts:
        return {"status": "skipped", "reason": "no Google accounts connected"}

    primary = await get_primary_account()
    if not primary:
        primary = accounts[0]

    primary_credentials = load_credentials(primary.id)
    if not primary_credentials:
        return {"status": "error", "reason": "could not load primary account credentials"}

    hours = LOOKBACK_HOURS.get(slot, 12)
    all_emails = []

    for account in accounts:
        credentials = load_credentials(account.id)
        if not credentials:
            logger.warning("Skipping account %s — no credentials", account.email)
            continue

        try:
            emails = list_recap_candidates(
                credentials,
                account_email=account.email,
                hours=hours,
                max_results=recap_settings.MAX_EMAILS_PER_ACCOUNT,
            )
            all_emails.extend(emails)
            logger.info("Fetched %s emails for %s", len(emails), account.email)
        except Exception as exc:
            logger.exception("Failed to fetch emails for %s: %s", account.email, exc)

    account_emails = [a.email for a in accounts]

    # Generate intelligent HTML recap
    recap_html = generate_intelligent_recap_html(
        slot=slot,
        emails=all_emails,
        account_emails=account_emails,
    )

    tz = pytz.timezone(recap_settings.TIMEZONE)
    now = datetime.now(tz)
    slot_label = SLOT_LABELS.get(slot, "Email")
    subject = f"{slot_label} Email Recap — {now.strftime('%a %b %d')}"

    recipient = recap_settings.RECIPIENT_OVERRIDE or primary.email

    try:
        sent = send_html_recap_email(
            primary_credentials,
            to=recipient,
            subject=subject,
            html_body=recap_html,
            text_body="Please view this email in an HTML-capable email client.",
        )
        logger.info("Sent %s recap to %s (message id %s)", slot, recipient, sent.get("id"))
        return {
            "status": "sent",
            "slot": slot,
            "recipient": recipient,
            "from_account": primary.email,
            "email_count": len(all_emails),
            "accounts_scanned": account_emails,
            "message_id": sent.get("id"),
        }
    except ValueError as exc:
        logger.warning("Recap email blocked: %s", exc)
        return {"status": "skipped", "reason": str(exc), "slot": slot}
    except Exception as exc:
        logger.exception("Failed to send recap email: %s", exc)
        return {"status": "error", "reason": str(exc)}
