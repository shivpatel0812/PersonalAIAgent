"""Parse email dates and check reply-window eligibility."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from app.agents.email_agent import settings as agent_settings


def parse_message_date(value: str | None) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    if "T" in text:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        dt = parsedate_to_datetime(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def is_within_reply_window(date_str: str | None) -> bool:
    """True when the message is recent enough to queue for reply."""
    parsed = parse_message_date(date_str)
    if not parsed:
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(days=agent_settings.REPLY_MAX_AGE_DAYS)
    return parsed >= cutoff
