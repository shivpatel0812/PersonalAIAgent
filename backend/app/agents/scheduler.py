"""APScheduler setup for autonomous agent jobs."""

from __future__ import annotations

import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents.email_recap import settings as recap_settings
from app.agents.email_agent import settings as email_agent_settings
from app.agents.email_agent.job import run_email_agent_scan
from app.agents.email_recap.job import run_email_recap

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """Start background scheduler for agent jobs."""
    global _scheduler

    recap_on = recap_settings.ENABLED
    agent_on = email_agent_settings.ENABLED

    if not recap_on and not agent_on:
        logger.info("Agent scheduler disabled")
        return

    if _scheduler is not None:
        return

    tz = pytz.timezone(recap_settings.TIMEZONE)
    _scheduler = AsyncIOScheduler(timezone=tz)

    if recap_on:
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

        times = ", ".join(
            f"{hour:02d}:{minute:02d}" for hour, minute, _ in recap_settings.SCHEDULE
        )
        logger.info("Email recap scheduled at %s %s", times, recap_settings.TIMEZONE)

    if agent_on:
        _scheduler.add_job(
            run_email_agent_scan,
            "interval",
            minutes=email_agent_settings.SCAN_INTERVAL_MINUTES,
            id="email_agent_scan",
            replace_existing=True,
            misfire_grace_time=600,
            coalesce=True,
        )
        logger.info(
            "Email agent scan every %s minutes",
            email_agent_settings.SCAN_INTERVAL_MINUTES,
        )

    _scheduler.start()
    logger.info("Agent scheduler started")


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
