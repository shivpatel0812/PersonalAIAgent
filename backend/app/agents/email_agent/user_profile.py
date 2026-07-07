"""Format global user profile for Email Agent prompts."""

from __future__ import annotations

from app.db.user_email_profile import UserEmailProfile


def format_profile_block(profile: UserEmailProfile | None) -> str:
    if not profile:
        return ""

    parts: list[str] = ["About the user:"]
    if profile.display_name:
        name_line = profile.display_name
        if profile.role_title:
            name_line = f"{profile.display_name}, {profile.role_title}"
        parts.append(f"- Name/role: {name_line}")
    elif profile.role_title:
        parts.append(f"- Role: {profile.role_title}")

    if profile.communication_style:
        parts.append(f"- Communication style: {profile.communication_style}")

    if profile.default_sign_off:
        parts.append(f"- Sign off with: {profile.default_sign_off}")

    if profile.expertise_areas:
        expertise = ", ".join(profile.expertise_areas)
        parts.append(f"- Expertise (mention when relevant): {expertise}")

    if len(parts) == 1:
        return ""

    return "\n".join(parts)


async def get_profile_block_with_defaults(user_id: str = "default") -> str:
    from app.db.google_accounts import get_primary_account
    from app.db.user_email_profile import get_profile

    profile = await get_profile(user_id)
    block = format_profile_block(profile)
    if block:
        return block

    primary = await get_primary_account()
    if not primary:
        return ""

    local = primary.email.split("@")[0]
    display_name = local.replace(".", " ").replace("_", " ").title()
    return (
        f"About the user:\n"
        f"- Name: {display_name}\n"
        f"- Sign off with: Best,"
    )
