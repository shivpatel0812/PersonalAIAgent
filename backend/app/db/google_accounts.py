"""
Database operations for Google accounts.
Handles multi-account OAuth token storage.
"""

from datetime import datetime
from typing import Any

from google.oauth2.credentials import Credentials

from app.supabase_client import get_supabase_client


class GoogleAccount:
    """Represents a connected Google account."""

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

    def to_credentials(self) -> Credentials:
        """Convert stored tokens to Google Credentials object."""
        return Credentials.from_authorized_user_info(self.tokens)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "account_label": self.account_label,
            "granted_scopes": self.granted_scopes,
            "is_primary": self.is_primary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


async def list_accounts() -> list[GoogleAccount]:
    """List all connected Google accounts."""
    supabase = get_supabase_client()
    result = supabase.table("google_accounts").select("*").order("created_at").execute()

    accounts = []
    for row in result.data:
        accounts.append(
            GoogleAccount(
                id=row["id"],
                email=row["email"],
                account_label=row.get("account_label"),
                tokens=row["tokens"],
                granted_scopes=row.get("granted_scopes", []),
                is_primary=row.get("is_primary", False),
                created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            )
        )
    return accounts


async def get_account(account_id: str) -> GoogleAccount | None:
    """Get a specific Google account by ID."""
    supabase = get_supabase_client()
    result = supabase.table("google_accounts").select("*").eq("id", account_id).execute()

    if not result.data:
        return None

    row = result.data[0]
    return GoogleAccount(
        id=row["id"],
        email=row["email"],
        account_label=row.get("account_label"),
        tokens=row["tokens"],
        granted_scopes=row.get("granted_scopes", []),
        is_primary=row.get("is_primary", False),
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )


async def get_primary_account() -> GoogleAccount | None:
    """Get the primary Google account."""
    supabase = get_supabase_client()
    result = supabase.table("google_accounts").select("*").eq("is_primary", True).execute()

    if not result.data:
        # If no primary, return the first account
        all_accounts = await list_accounts()
        return all_accounts[0] if all_accounts else None

    row = result.data[0]
    return GoogleAccount(
        id=row["id"],
        email=row["email"],
        account_label=row.get("account_label"),
        tokens=row["tokens"],
        granted_scopes=row.get("granted_scopes", []),
        is_primary=row.get("is_primary", False),
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )


async def save_account(
    credentials: Credentials,
    email: str,
    account_label: str | None = None,
    is_primary: bool = False,
) -> GoogleAccount:
    """
    Save or update a Google account.

    Args:
        credentials: Google OAuth credentials
        email: Account email address
        account_label: Optional label (e.g., "Work", "Personal")
        is_primary: Whether this should be the primary account

    Returns:
        The saved GoogleAccount
    """
    supabase = get_supabase_client()

    # Convert credentials to dict for storage
    scopes = credentials.scopes or []
    tokens = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": scopes,
    }

    # Check if account already exists
    existing = supabase.table("google_accounts").select("*").eq("email", email).execute()

    if existing.data:
        # Update existing account
        account_id = existing.data[0]["id"]

        # If setting as primary, unset other primaries
        if is_primary:
            supabase.table("google_accounts").update({"is_primary": False}).eq(
                "is_primary", True
            ).execute()

        result = (
            supabase.table("google_accounts")
            .update(
                {
                    "tokens": tokens,
                    "granted_scopes": scopes,
                    "account_label": account_label,
                    "is_primary": is_primary,
                }
            )
            .eq("id", account_id)
            .execute()
        )
    else:
        # If setting as primary, unset other primaries
        if is_primary:
            supabase.table("google_accounts").update({"is_primary": False}).eq(
                "is_primary", True
            ).execute()

        # If this is the first account, make it primary
        accounts_count = len((await list_accounts()))
        if accounts_count == 0:
            is_primary = True

        # Create new account
        result = (
            supabase.table("google_accounts")
            .insert(
                {
                    "email": email,
                    "tokens": tokens,
                    "granted_scopes": scopes,
                    "account_label": account_label,
                    "is_primary": is_primary,
                }
            )
            .execute()
        )

    row = result.data[0]
    return GoogleAccount(
        id=row["id"],
        email=row["email"],
        account_label=row.get("account_label"),
        tokens=row["tokens"],
        granted_scopes=row.get("granted_scopes", []),
        is_primary=row.get("is_primary", False),
        created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
    )


async def delete_account(account_id: str) -> bool:
    """
    Delete a Google account.

    Args:
        account_id: Account ID to delete

    Returns:
        True if deleted successfully
    """
    supabase = get_supabase_client()

    # Check if this was the primary account
    account = await get_account(account_id)
    was_primary = account.is_primary if account else False

    # Delete the account
    supabase.table("google_accounts").delete().eq("id", account_id).execute()

    # If it was primary, make the first remaining account primary
    if was_primary:
        remaining = await list_accounts()
        if remaining:
            await set_primary_account(remaining[0].id)

    return True


async def set_primary_account(account_id: str) -> GoogleAccount | None:
    """
    Set an account as the primary account.

    Args:
        account_id: Account ID to set as primary

    Returns:
        The updated account, or None if not found
    """
    supabase = get_supabase_client()

    # Unset all primaries
    supabase.table("google_accounts").update({"is_primary": False}).eq(
        "is_primary", True
    ).execute()

    # Set this one as primary
    result = (
        supabase.table("google_accounts")
        .update({"is_primary": True})
        .eq("id", account_id)
        .execute()
    )

    if not result.data:
        return None

    return await get_account(account_id)


async def update_account_label(account_id: str, label: str | None) -> GoogleAccount | None:
    """
    Update an account's label.

    Args:
        account_id: Account ID
        label: New label (e.g., "Work", "Personal")

    Returns:
        The updated account, or None if not found
    """
    supabase = get_supabase_client()

    result = (
        supabase.table("google_accounts")
        .update({"account_label": label})
        .eq("id", account_id)
        .execute()
    )

    if not result.data:
        return None

    return await get_account(account_id)
