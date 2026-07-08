"""Robinhood Agentic Trading MCP OAuth (PKCE + dynamic client registration)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.db.robinhood_connections import (
    get_connection,
    get_oauth_client_id,
    pop_oauth_state,
    save_connection,
    save_oauth_client_id,
    save_oauth_state,
)

MCP_OAUTH_METADATA_URL = "https://agent.robinhood.com/.well-known/oauth-authorization-server"
REGISTER_URL = "https://agent.robinhood.com/oauth/trading/register"
SCOPE = "internal"


def _redirect_uri() -> str:
    return settings.robinhood_redirect_uri


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def _register_client(redirect_uri: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            REGISTER_URL,
            json={
                "client_name": "Personal AI Agent",
                "redirect_uris": [redirect_uri],
            },
        )
        response.raise_for_status()
        data = response.json()
    client_id = data["client_id"]
    await save_oauth_client_id(client_id=client_id, redirect_uri=redirect_uri)
    return client_id


async def get_client_id() -> str:
    redirect_uri = _redirect_uri()
    existing = await get_oauth_client_id(redirect_uri=redirect_uri)
    if existing:
        return existing
    return await _register_client(redirect_uri)


async def get_authorization_url() -> str:
    client_id = await get_client_id()
    code_verifier, code_challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    await save_oauth_state(state=state, code_verifier=code_verifier)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _redirect_uri(),
        "scope": SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://robinhood.com/oauth?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, state: str) -> None:
    code_verifier = await pop_oauth_state(state)
    if not code_verifier:
        raise RuntimeError("Invalid or expired OAuth state")

    client_id = await get_client_id()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.robinhood.com/oauth2/token/",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "redirect_uri": _redirect_uri(),
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()

    expires_at = None
    if data.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))

    await save_connection(
        client_id=client_id,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
    )


async def refresh_access_token_if_needed() -> str | None:
    connection = await get_connection()
    if not connection:
        return None

    if connection.expires_at:
        expires = connection.expires_at
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if expires > datetime.now(timezone.utc) + timedelta(minutes=2):
            return connection.access_token

    if not connection.refresh_token:
        return connection.access_token

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.robinhood.com/oauth2/token/",
            data={
                "grant_type": "refresh_token",
                "refresh_token": connection.refresh_token,
                "client_id": connection.client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()

    expires_at = None
    if data.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))

    updated = await save_connection(
        client_id=connection.client_id,
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token") or connection.refresh_token,
        expires_at=expires_at,
    )
    return updated.access_token


async def has_stored_credentials() -> bool:
    connection = await get_connection()
    return connection is not None and bool(connection.access_token)
