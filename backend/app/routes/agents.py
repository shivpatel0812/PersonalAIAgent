from typing import Literal

from fastapi import APIRouter, HTTPException

from app.agents.email_recap import settings as recap_settings
from app.agents.email_agent import settings as email_agent_settings
from app.agents.email_agent.job import run_email_agent_scan
from app.agents.email_recap.job import run_email_recap
from app.agents.scheduler import scheduler_running
from app.google.email_safety import (
    OUTBOUND_EMAIL_ENABLED,
    ONLY_CONNECTED_ACCOUNT_RECIPIENTS,
    get_connected_account_emails,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/email-recap/status")
def email_recap_status() -> dict:
    """Check whether the email recap agent is enabled and scheduled."""
    schedule = [
        {
            "slot": slot,
            "time": f"{hour:02d}:{minute:02d}",
        }
        for hour, minute, slot in recap_settings.SCHEDULE
    ]
    return {
        "enabled": recap_settings.ENABLED,
        "scheduler_running": scheduler_running(),
        "timezone": recap_settings.TIMEZONE,
        "schedule": schedule,
        "max_emails_per_account": recap_settings.MAX_EMAILS_PER_ACCOUNT,
        "recipient_override": recap_settings.RECIPIENT_OVERRIDE or None,
        "outbound_email_enabled": OUTBOUND_EMAIL_ENABLED,
        "only_connected_account_recipients": ONLY_CONNECTED_ACCOUNT_RECIPIENTS,
        "allowed_recipients": get_connected_account_emails(),
    }


@router.post("/email-recap/run")
async def trigger_email_recap(
    slot: Literal["morning", "noon", "evening", "night"] = "morning",
) -> dict:
    """Manually run the email recap agent (useful for testing)."""
    if not recap_settings.ENABLED:
        raise HTTPException(status_code=503, detail="Email recap agent is disabled")

    result = await run_email_recap(slot=slot)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Recap failed"))

    return result


@router.get("/email-agent/status")
async def email_agent_status() -> dict:
    from app.db.email_agent import count_active_items

    return {
        "enabled": email_agent_settings.ENABLED,
        "scheduler_running": scheduler_running(),
        "scan_interval_minutes": email_agent_settings.SCAN_INTERVAL_MINUTES,
        "active_count": await count_active_items(),
        "max_queue_size": email_agent_settings.MAX_ACTIVE_QUEUE_SIZE,
    }


@router.post("/email-agent/run")
async def trigger_email_agent() -> dict:
    """Manually run the email agent inbox scan."""
    if not email_agent_settings.ENABLED:
        raise HTTPException(status_code=503, detail="Email agent is disabled")

    result = await run_email_agent_scan()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Scan failed"))

    return result
