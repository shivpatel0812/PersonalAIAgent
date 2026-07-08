"""Database operations for Robinhood MCP OAuth connections."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.supabase_client import get_supabase_client


class RobinhoodConnection:
    def __init__(self, row: dict[str, Any]):
        self.id = row["id"]
        self.user_id = row.get("user_id", "default")
        self.client_id = row["client_id"]
        self.access_token = row["access_token"]
        self.refresh_token = row.get("refresh_token")
        self.expires_at = row.get("expires_at")
        self.scopes = row.get("scopes") or ["internal"]
        self.account_label = row.get("account_label")
        self.created_at = row.get("created_at")
        self.updated_at = row.get("updated_at")


async def get_connection(user_id: str = "default") -> RobinhoodConnection | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("robinhood_connections")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return RobinhoodConnection(result.data[0])


async def save_connection(
    *,
    client_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime | None,
    user_id: str = "default",
) -> RobinhoodConnection:
    supabase = get_supabase_client()
    payload = {
        "user_id": user_id,
        "client_id": client_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    existing = await get_connection(user_id=user_id)
    if existing:
        result = (
            supabase.table("robinhood_connections")
            .update(payload)
            .eq("id", existing.id)
            .execute()
        )
    else:
        result = supabase.table("robinhood_connections").insert(payload).execute()
    return RobinhoodConnection(result.data[0])


async def delete_connection(user_id: str = "default") -> bool:
    supabase = get_supabase_client()
    result = supabase.table("robinhood_connections").delete().eq("user_id", user_id).execute()
    return bool(result.data)


async def get_oauth_client_id(*, redirect_uri: str, user_id: str = "default") -> str | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("robinhood_oauth_clients")
        .select("client_id")
        .eq("user_id", user_id)
        .eq("redirect_uri", redirect_uri)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]["client_id"]


async def save_oauth_client_id(
    *,
    client_id: str,
    redirect_uri: str,
    user_id: str = "default",
) -> None:
    supabase = get_supabase_client()
    existing = await get_oauth_client_id(redirect_uri=redirect_uri, user_id=user_id)
    if existing:
        return
    supabase.table("robinhood_oauth_clients").insert(
        {
            "user_id": user_id,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
    ).execute()


async def save_oauth_state(*, state: str, code_verifier: str, user_id: str = "default") -> None:
    supabase = get_supabase_client()
    supabase.table("robinhood_oauth_states").insert(
        {
            "state": state,
            "user_id": user_id,
            "code_verifier": code_verifier,
        }
    ).execute()


async def pop_oauth_state(state: str) -> str | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("robinhood_oauth_states")
        .select("code_verifier")
        .eq("state", state)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    code_verifier = result.data[0]["code_verifier"]
    supabase.table("robinhood_oauth_states").delete().eq("state", state).execute()
    return code_verifier
