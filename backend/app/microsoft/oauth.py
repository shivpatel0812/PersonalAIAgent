"""Microsoft OAuth and token management for Outlook / Graph API."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

import msal

from app.config import settings
from app.db.microsoft_accounts import (
    get_account,
    get_primary_account,
    list_accounts,
    save_account,
)

GRAPH_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
]


def _authority() -> str:
    tenant = settings.microsoft_tenant_id or "common"
    return f"https://login.microsoftonline.com/{tenant}"


def _msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        settings.microsoft_client_id,
        authority=_authority(),
        client_credential=settings.microsoft_client_secret,
    )


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def get_authorization_url(*, select_account: bool = False) -> str:
    app = _msal_app()
    prompt = "select_account" if select_account else None
    kwargs: dict[str, Any] = {}
    if prompt:
        kwargs["prompt"] = prompt
    return app.get_authorization_request_url(
        GRAPH_SCOPES,
        redirect_uri=settings.microsoft_redirect_uri,
        **kwargs,
    )


def exchange_code_for_credentials(code: str) -> tuple[dict[str, Any], str]:
    app = _msal_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=GRAPH_SCOPES,
        redirect_uri=settings.microsoft_redirect_uri,
    )
    if "error" in result:
        raise RuntimeError(result.get("error_description") or result.get("error"))

    access_token = result.get("access_token")
    if not access_token:
        raise RuntimeError("Microsoft OAuth did not return an access token")

    email = _fetch_user_email(access_token)
    tokens = {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "token_type": result.get("token_type", "Bearer"),
        "scope": result.get("scope"),
        "id_token_claims": result.get("id_token_claims"),
    }
    scopes = (result.get("scope") or "").split()

    async def _save() -> str:
        account = await save_account(
            tokens=tokens,
            email=email,
            granted_scopes=scopes,
        )
        return account.id

    account_id = _run_async(_save())
    return tokens, account_id


def _fetch_user_email(access_token: str) -> str:
    import httpx

    response = httpx.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    email = data.get("mail") or data.get("userPrincipalName")
    if not email:
        raise RuntimeError("Could not resolve Microsoft account email")
    return email.lower()


def load_tokens(account_id: str | None = None) -> dict[str, Any] | None:
    async def _load() -> dict[str, Any] | None:
        if account_id:
            account = await get_account(account_id)
        else:
            account = await get_primary_account()
        if not account:
            return None
        return await refresh_tokens_if_needed(account.tokens, account.id)

    return _run_async(_load())


async def refresh_tokens_if_needed(tokens: dict[str, Any], account_id: str) -> dict[str, Any]:
    from app.db.microsoft_accounts import get_account, save_account as db_save

    account = await get_account(account_id)
    if not account:
        return tokens

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return tokens

    app = _msal_app()
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=GRAPH_SCOPES)
    if "error" in result or not result.get("access_token"):
        return tokens

    updated = {
        **tokens,
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token") or refresh_token,
        "expires_in": result.get("expires_in"),
        "scope": result.get("scope", tokens.get("scope")),
    }
    scopes = (updated.get("scope") or "").split() if isinstance(updated.get("scope"), str) else account.granted_scopes
    await db_save(
        tokens=updated,
        email=account.email,
        granted_scopes=scopes,
        account_label=account.account_label,
        is_primary=account.is_primary,
    )
    return updated


def has_stored_credentials() -> bool:
    try:
        accounts = _run_async(list_accounts())
        return len(accounts) > 0
    except Exception:
        return False


def get_access_token(account_id: str | None = None) -> str | None:
    tokens = load_tokens(account_id)
    if not tokens:
        return None
    return tokens.get("access_token")
