from typing import Literal

from fastapi import APIRouter, HTTPException

from app.agents.email_recap.job import run_email_recap
from app.agents.scheduler import scheduler_running
from app.config import settings

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/email-recap/status")
def email_recap_status() -> dict:
    """Check whether the email recap agent is enabled and scheduled."""
    return {
        "enabled": settings.email_recap_enabled,
        "scheduler_running": scheduler_running(),
        "timezone": settings.email_recap_timezone,
        "morning": f"{settings.email_recap_morning_hour:02d}:{settings.email_recap_morning_minute:02d}",
        "evening": f"{settings.email_recap_evening_hour:02d}:{settings.email_recap_evening_minute:02d}",
        "max_emails_per_account": settings.email_recap_max_emails_per_account,
        "recipient_override": settings.email_recap_recipient or None,
    }


@router.post("/email-recap/run")
async def trigger_email_recap(
    slot: Literal["morning", "evening"] = "morning",
) -> dict:
    """Manually run the email recap agent (useful for testing)."""
    if not settings.email_recap_enabled:
        raise HTTPException(status_code=503, detail="Email recap agent is disabled")

    result = await run_email_recap(slot=slot)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Recap failed"))

    return result
