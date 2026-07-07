"""Sender priority and relationship context for Email Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.agents.email_agent import settings as agent_settings

logger = logging.getLogger(__name__)

_last_priority_update: datetime | None = None
MIN_RATINGS_FOR_AUTO_ARCHIVE = 3
PRIORITY_UPDATE_INTERVAL_DAYS = 7


@dataclass
class SenderContext:
    sender: str
    priority_score: float = 0.0
    avg_star_rating: float | None = None
    total_ratings: int = 0
    reply_rate: float | None = None
    avg_response_time_minutes: int | None = None
    always_urgent: bool = False
    auto_archive: bool = False


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    match = re.search(r"<([^>]+)>", email)
    if match:
        return match.group(1).strip().lower()
    return email


async def get_sender_context(
    sender_email: str,
    user_id: str = "default",
) -> SenderContext | None:
    if not agent_settings.SENDER_INTELLIGENCE_ENABLED:
        return None

    sender = _normalize_email(sender_email)
    if not sender:
        return None

    try:
        from app.supabase_client import get_supabase_client

        supabase = get_supabase_client()
        result = (
            supabase.table("sender_priorities")
            .select("*")
            .eq("user_id", user_id)
            .eq("sender", sender)
            .execute()
        )
        if not result.data:
            return None

        row = result.data[0]
        return SenderContext(
            sender=sender,
            priority_score=float(row.get("priority_score") or 0),
            avg_star_rating=float(row["avg_star_rating"])
            if row.get("avg_star_rating") is not None
            else None,
            total_ratings=int(row.get("total_ratings") or 0),
            reply_rate=float(row["reply_rate"]) if row.get("reply_rate") is not None else None,
            avg_response_time_minutes=row.get("avg_response_time_minutes"),
            always_urgent=bool(row.get("always_urgent")),
            auto_archive=bool(row.get("auto_archive")),
        )
    except Exception as exc:
        logger.warning("Failed to load sender context for %s: %s", sender, exc)
        return None


def should_auto_archive(context: SenderContext | None) -> bool:
    if not context or not context.auto_archive:
        return False
    return context.total_ratings >= MIN_RATINGS_FOR_AUTO_ARCHIVE


def format_sender_context_block(context: SenderContext | None) -> str:
    if not context:
        return ""

    lines = ["Sender relationship context:"]

    score = context.priority_score
    if score >= 0.4:
        priority_label = "high — you usually prioritize this sender"
    elif score <= -0.2:
        priority_label = "low — brief replies are fine"
    else:
        priority_label = "normal"

    lines.append(f"- Priority score: {score:+.2f} ({priority_label})")

    if context.avg_star_rating is not None and context.total_ratings:
        lines.append(
            f"- Avg rating: {context.avg_star_rating:.1f}/5 "
            f"({context.total_ratings} ratings)"
        )

    if context.reply_rate is not None:
        lines.append(f"- Reply rate: {context.reply_rate * 100:.0f}%")

    if context.avg_response_time_minutes:
        lines.append(f"- Typical reply time: ~{context.avg_response_time_minutes} min")

    if context.always_urgent:
        lines.append("- Flag: always_urgent (respond promptly and thoroughly)")

    return "\n".join(lines)


def candidate_sort_key(context: SenderContext | None) -> tuple[int, float]:
    """Sort: always_urgent first, then higher priority_score."""
    if not context:
        return (0, 0.0)
    urgent = 1 if context.always_urgent else 0
    return (urgent, context.priority_score)


async def maybe_refresh_sender_priorities() -> None:
    """Debounced refresh of sender_priorities after replies."""
    global _last_priority_update

    now = datetime.now(timezone.utc)
    if _last_priority_update:
        elapsed = now - _last_priority_update
        if elapsed < timedelta(days=PRIORITY_UPDATE_INTERVAL_DAYS):
            return

    try:
        from app.supabase_client import get_supabase_client

        supabase = get_supabase_client()
        supabase.rpc("update_sender_priorities").execute()
        _last_priority_update = now
        logger.info("Refreshed sender_priorities")
    except Exception as exc:
        logger.warning("Failed to refresh sender_priorities: %s", exc)
