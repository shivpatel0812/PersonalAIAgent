"""Database operations for Microsoft / Outlook accounts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.supabase_client import get_supabase_client


class MicrosoftAccount:
    def __init__(
        self,
        id: str,
        email: str,
        tokens: dict[str, Any],
        granted_scopes: list[str],
        account_label: str | None = None,
        is_primary: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.email = email
        self.account_label = account_label
        self.tokens = tokens
        self.granted_scopes = granted_scopes
        self.is_primary = is_primary
        self.created_at = created_at
        self.updated_at = updated_at


def _row_to_account(row: dict[str, Any]) -> MicrosoftAccount:
    return MicrosoftAccount(
        id=row["id"],
        email=row["email"],
        account_label=row.get("account_label"),
        tokens=row["tokens"],
        granted_scopes=row.get("granted_scopes", []),
        is_primary=row.get("is_primary", False),
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )


async def list_accounts() -> list[MicrosoftAccount]:
    supabase = get_supabase_client()
    result = supabase.table("microsoft_accounts").select("*").order("created_at").execute()
    return [_row_to_account(row) for row in result.data]


async def get_account(account_id: str) -> MicrosoftAccount | None:
    supabase = get_supabase_client()
    result = supabase.table("microsoft_accounts").select("*").eq("id", account_id).execute()
    if not result.data:
        return None
    return _row_to_account(result.data[0])


async def get_primary_account() -> MicrosoftAccount | None:
    supabase = get_supabase_client()
    result = supabase.table("microsoft_accounts").select("*").eq("is_primary", True).execute()
    if not result.data:
        accounts = await list_accounts()
        return accounts[0] if accounts else None
    return _row_to_account(result.data[0])


async def save_account(
    *,
    tokens: dict[str, Any],
    email: str,
    granted_scopes: list[str],
    account_label: str | None = None,
    is_primary: bool = False,
) -> MicrosoftAccount:
    supabase = get_supabase_client()
    existing = supabase.table("microsoft_accounts").select("*").eq("email", email).execute()

    if existing.data:
        row = existing.data[0]
        account_id = row["id"]
        resolved_is_primary = is_primary or row.get("is_primary", False)
        if resolved_is_primary:
            supabase.table("microsoft_accounts").update({"is_primary": False}).eq(
                "is_primary", True
            ).execute()
        result = (
            supabase.table("microsoft_accounts")
            .update(
                {
                    "tokens": tokens,
                    "granted_scopes": granted_scopes,
                    "account_label": account_label,
                    "is_primary": resolved_is_primary,
                }
            )
            .eq("id", account_id)
            .execute()
        )
    else:
        if is_primary:
            supabase.table("microsoft_accounts").update({"is_primary": False}).eq(
                "is_primary", True
            ).execute()
        if len(await list_accounts()) == 0:
            is_primary = True
        result = (
            supabase.table("microsoft_accounts")
            .insert(
                {
                    "email": email,
                    "tokens": tokens,
                    "granted_scopes": granted_scopes,
                    "account_label": account_label,
                    "is_primary": is_primary,
                }
            )
            .execute()
        )

    return _row_to_account(result.data[0])


async def delete_account(account_id: str) -> bool:
    supabase = get_supabase_client()
    account = await get_account(account_id)
    was_primary = account.is_primary if account else False
    supabase.table("microsoft_accounts").delete().eq("id", account_id).execute()
    if was_primary:
        remaining = await list_accounts()
        if remaining:
            await set_primary_account(remaining[0].id)
    return True


async def set_primary_account(account_id: str) -> MicrosoftAccount | None:
    supabase = get_supabase_client()
    supabase.table("microsoft_accounts").update({"is_primary": False}).eq(
        "is_primary", True
    ).execute()
    result = (
        supabase.table("microsoft_accounts")
        .update({"is_primary": True})
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        return None
    return await get_account(account_id)


async def update_account_label(account_id: str, label: str | None) -> MicrosoftAccount | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("microsoft_accounts")
        .update({"account_label": label})
        .eq("id", account_id)
        .execute()
    )
    if not result.data:
        return None
    return await get_account(account_id)
