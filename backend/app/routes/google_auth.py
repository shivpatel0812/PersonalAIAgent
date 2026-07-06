from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.google.oauth import (
    clear_credentials,
    exchange_code_for_credentials,
    get_authorization_url,
    has_stored_credentials,
    test_calendar_access,
)

router = APIRouter(prefix="/auth/google", tags=["google-auth"])


class GoogleCalendarStatus(BaseModel):
    configured: bool
    connected: bool
    calendar_access: bool
    calendar_summary: str | None = None
    upcoming_events_sample: int | None = None
    connect_url: str | None = None
    redirect_uri: str | None = None
    oauth_client_id: str | None = None
    message: str


@router.get("/status", response_model=GoogleCalendarStatus)
def google_calendar_status() -> GoogleCalendarStatus:
    configured = settings.google_oauth_configured
    connected = configured and has_stored_credentials()

    redirect_uri = settings.google_redirect_uri if configured else None
    oauth_client_id = settings.google_client_id if configured else None

    if not configured:
        return GoogleCalendarStatus(
            configured=False,
            connected=False,
            calendar_access=False,
            redirect_uri=redirect_uri,
            oauth_client_id=oauth_client_id,
            message="Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env",
        )

    if not connected:
        return GoogleCalendarStatus(
            configured=True,
            connected=False,
            calendar_access=False,
            connect_url="/auth/google/connect",
            redirect_uri=redirect_uri,
            oauth_client_id=oauth_client_id,
            message="OAuth credentials found. Connect your Google account to test Calendar access.",
        )

    test_result = test_calendar_access()
    return GoogleCalendarStatus(
        configured=True,
        connected=bool(test_result.get("connected")),
        calendar_access=bool(test_result.get("calendar_access")),
        calendar_summary=test_result.get("calendar_summary"),
        upcoming_events_sample=test_result.get("upcoming_events_sample"),
        connect_url="/auth/google/connect",
        redirect_uri=redirect_uri,
        oauth_client_id=oauth_client_id,
        message=str(test_result.get("message", "")),
    )


@router.get("/connect")
def google_calendar_connect():
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Add credentials to .env first.",
        )

    return RedirectResponse(url=get_authorization_url())


@router.get("/callback")
def google_calendar_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}?google_calendar=error&message={error}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    try:
        exchange_code_for_credentials(code)
    except Exception as exc:
        return RedirectResponse(
            url=f"{settings.frontend_url}?google_calendar=error&message={exc}"
        )

    return RedirectResponse(url=f"{settings.frontend_url}?google_calendar=connected")


@router.post("/disconnect")
def google_calendar_disconnect() -> dict[str, str]:
    clear_credentials()
    return {"status": "disconnected", "message": "Google Calendar token removed. Connect again to re-authorize."}
