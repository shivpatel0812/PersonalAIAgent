from typing import Literal

from fastapi import APIRouter, HTTPException

from app.agents.email_recap import settings as recap_settings
from app.agents.email_recap.job import run_email_recap
from app.agents.scheduler import scheduler_running

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/email-recap/status")
def email_recap_status() -> dict:
    """Check whether the email recap agent is enabled and scheduled."""
    return {
        "enabled": recap_settings.ENABLED,
        "scheduler_running": scheduler_running(),
        "timezone": recap_settings.TIMEZONE,
        "morning": f"{recap_settings.MORNING_HOUR:02d}:{recap_settings.MORNING_MINUTE:02d}",
        "evening": f"{recap_settings.EVENING_HOUR:02d}:{recap_settings.EVENING_MINUTE:02d}",
        "max_emails_per_account": recap_settings.MAX_EMAILS_PER_ACCOUNT,
        "recipient_override": recap_settings.RECIPIENT_OVERRIDE or None,
    }


@router.post("/email-recap/run")
async def trigger_email_recap(
    slot: Literal["morning", "evening"] = "morning",
) -> dict:
    """Manually run the email recap agent (useful for testing)."""
    if not recap_settings.ENABLED:
        raise HTTPException(status_code=503, detail="Email recap agent is disabled")

    result = await run_email_recap(slot=slot)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Recap failed"))

    return result
