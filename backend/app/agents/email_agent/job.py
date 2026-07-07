"""Scheduled Email Agent scan job."""

from __future__ import annotations

import logging

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.service import scan_for_reply_candidates

logger = logging.getLogger(__name__)


async def run_email_agent_scan() -> dict:
    if not agent_settings.ENABLED:
        return {"status": "skipped", "reason": "email agent disabled"}

    result = await scan_for_reply_candidates()
    logger.info("Email agent scan: %s", result)
    return result
