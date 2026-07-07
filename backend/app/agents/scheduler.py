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

    _scheduler.add_job(
        run_email_recap,
        CronTrigger(
            hour=recap_settings.MORNING_HOUR,
            minute=recap_settings.MORNING_MINUTE,
            timezone=tz,
        ),
        kwargs={"slot": "morning"},
        id="email_recap_morning",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    _scheduler.add_job(
        run_email_recap,
        CronTrigger(
            hour=recap_settings.EVENING_HOUR,
            minute=recap_settings.EVENING_MINUTE,
            timezone=tz,
        ),
        kwargs={"slot": "evening"},
        id="email_recap_evening",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    _scheduler.start()
    logger.info(
        "Agent scheduler started — email recap at %02d:%02d and %02d:%02d %s",
        recap_settings.MORNING_HOUR,
        recap_settings.MORNING_MINUTE,
        recap_settings.EVENING_HOUR,
        recap_settings.EVENING_MINUTE,
        recap_settings.TIMEZONE,
    )


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
