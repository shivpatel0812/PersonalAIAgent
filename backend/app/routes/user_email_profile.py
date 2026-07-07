from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.user_email_profile import get_profile, upsert_profile

router = APIRouter(prefix="/user", tags=["user"])


class EmailProfileUpdate(BaseModel):
    displayName: str | None = None
    roleTitle: str | None = None
    communicationStyle: str | None = None
    defaultSignOff: str | None = None
    expertiseAreas: list[str] | None = None
    timezone: str | None = None


@router.get("/email-profile")
async def get_email_profile() -> dict:
    profile = await get_profile()
    if not profile:
        return {
            "displayName": "",
            "roleTitle": "",
            "communicationStyle": "",
            "defaultSignOff": "",
            "expertiseAreas": [],
            "timezone": "America/Los_Angeles",
        }
    return profile.to_api_dict()


@router.put("/email-profile")
async def update_email_profile(body: EmailProfileUpdate) -> dict:
    profile = await upsert_profile(
        display_name=body.displayName,
        role_title=body.roleTitle,
        communication_style=body.communicationStyle,
        default_sign_off=body.defaultSignOff,
        expertise_areas=body.expertiseAreas,
        timezone=body.timezone,
    )
    return profile.to_api_dict()
