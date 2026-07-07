"""APScheduler setup for autonomous agent jobs."""

from __future__ import annotations

import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents.email_recap import settings as recap_settings
from app.agents.email_recap.job import run_email_recap

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """Start background scheduler for agent jobs."""
    global _scheduler

    if not recap_settings.ENABLED:
        logger.info("Email recap scheduler disabled")
        return

    if _scheduler is not None:
        return

    tz = pytz.timezone(recap_settings.TIMEZONE)
    _scheduler = AsyncIOScheduler(timezone=tz)

    for hour, minute, slot in recap_settings.SCHEDULE:
        _scheduler.add_job(
            run_email_recap,
            CronTrigger(hour=hour, minute=minute, timezone=tz),
            kwargs={"slot": slot},
            id=f"email_recap_{slot}",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )

    _scheduler.start()

    times = ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute, _ in recap_settings.SCHEDULE)
    logger.info("Agent scheduler started — email recap at %s %s", times, recap_settings.TIMEZONE)


def shutdown_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler

    if _scheduler is None:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Agent scheduler stopped")


def scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running
