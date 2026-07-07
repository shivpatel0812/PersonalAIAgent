"""Database operations for global Email Agent user profile."""

from __future__ import annotations

from typing import Any

from app.supabase_client import get_supabase_client

DEFAULT_TIMEZONE = "America/Los_Angeles"


class UserEmailProfile:
    def __init__(self, row: dict[str, Any]):
        self.user_id = row.get("user_id", "default")
        self.display_name = row.get("display_name")
        self.role_title = row.get("role_title")
        self.communication_style = row.get("communication_style")
        self.default_sign_off = row.get("default_sign_off")
        self.expertise_areas = row.get("expertise_areas") or []
        self.timezone = row.get("timezone") or DEFAULT_TIMEZONE
        self.updated_at = row.get("updated_at")

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "displayName": self.display_name or "",
            "roleTitle": self.role_title or "",
            "communicationStyle": self.communication_style or "",
            "defaultSignOff": self.default_sign_off or "",
            "expertiseAreas": self.expertise_areas,
            "timezone": self.timezone,
        }


def _row_to_profile(row: dict[str, Any]) -> UserEmailProfile:
    return UserEmailProfile(row)


async def get_profile(user_id: str = "default") -> UserEmailProfile | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("user_email_profiles")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_profile(result.data[0])


async def upsert_profile(
    *,
    user_id: str = "default",
    display_name: str | None = None,
    role_title: str | None = None,
    communication_style: str | None = None,
    default_sign_off: str | None = None,
    expertise_areas: list[str] | None = None,
    timezone: str | None = None,
) -> UserEmailProfile:
    supabase = get_supabase_client()
    existing = await get_profile(user_id)

    payload: dict[str, Any] = {"user_id": user_id}
    if display_name is not None:
        payload["display_name"] = display_name or None
    if role_title is not None:
        payload["role_title"] = role_title or None
    if communication_style is not None:
        payload["communication_style"] = communication_style or None
    if default_sign_off is not None:
        payload["default_sign_off"] = default_sign_off or None
    if expertise_areas is not None:
        payload["expertise_areas"] = expertise_areas
    if timezone is not None:
        payload["timezone"] = timezone or DEFAULT_TIMEZONE

    if existing:
        result = (
            supabase.table("user_email_profiles")
            .update(payload)
            .eq("user_id", user_id)
            .execute()
        )
    else:
        if "timezone" not in payload:
            payload["timezone"] = DEFAULT_TIMEZONE
        result = supabase.table("user_email_profiles").insert(payload).execute()

    return _row_to_profile(result.data[0])
