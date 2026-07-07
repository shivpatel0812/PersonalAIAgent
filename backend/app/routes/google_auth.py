from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.db.google_accounts import (
    get_account,
    get_primary_account,
    list_accounts,
    set_primary_account,
    update_account_label,
)
from app.db.google_accounts import delete_account as db_delete_account
from app.google.oauth import (
    SCOPE_GROUPS,
    build_scopes_from_services,
    clear_credentials,
    exchange_code_for_credentials,
    get_authorization_url,
    get_granted_services,
    get_service_from_scope,
    has_stored_credentials,
    migrate_legacy_token_to_db,
    test_calendar_access,
)

router = APIRouter(prefix="/auth/google", tags=["google-auth"])


class ServiceInfo(BaseModel):
    name: str
    label: str
    description: str
    scopes: list[str]


class AvailableServicesResponse(BaseModel):
    services: list[ServiceInfo]


class GoogleCalendarStatus(BaseModel):
    configured: bool
    connected: bool
    calendar_access: bool
    gmail_access: bool = False
    drive_access: bool = False
    granted_services: list[str] = []
    calendar_summary: str | None = None
    upcoming_events_sample: int | None = None
    connect_url: str | None = None
    redirect_uri: str | None = None
    oauth_client_id: str | None = None
    message: str


class AccountInfo(BaseModel):
    id: str
    email: str
    account_label: str | None
    granted_services: list[str]
    is_primary: bool
    created_at: str | None
    updated_at: str | None


class AccountsListResponse(BaseModel):
    accounts: list[AccountInfo]


class UpdateAccountLabelRequest(BaseModel):
    label: str | None


@router.get("/services", response_model=AvailableServicesResponse)
def get_available_services() -> AvailableServicesResponse:
    """Get list of available Google services that can be connected."""
    services = [
        ServiceInfo(
            name="gmail",
            label="Gmail",
            description="Read, send, and manage emails",
            scopes=SCOPE_GROUPS["gmail"],
        ),
        ServiceInfo(
            name="calendar",
            label="Calendar",
            description="View and manage calendar events",
            scopes=SCOPE_GROUPS["calendar"],
        ),
        ServiceInfo(
            name="drive",
            label="Drive & Docs",
            description="Access files and Google Docs",
            scopes=SCOPE_GROUPS["drive"],
        ),
        ServiceInfo(
            name="sheets",
            label="Sheets",
            description="Read and write spreadsheet data",
            scopes=SCOPE_GROUPS["sheets"],
        ),
        ServiceInfo(
            name="youtube",
            label="YouTube",
            description="Access personal YouTube data",
            scopes=SCOPE_GROUPS["youtube"],
        ),
    ]
    return AvailableServicesResponse(services=services)


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
    granted_services = get_granted_services()

    return GoogleCalendarStatus(
        configured=True,
        connected=bool(test_result.get("connected")),
        calendar_access=bool(test_result.get("calendar_access")),
        gmail_access=bool(test_result.get("gmail_access")),
        drive_access=bool(test_result.get("drive_access")),
        granted_services=granted_services,
        calendar_summary=test_result.get("calendar_summary"),
        upcoming_events_sample=test_result.get("upcoming_events_sample"),
        connect_url="/auth/google/connect",
        redirect_uri=redirect_uri,
        oauth_client_id=oauth_client_id,
        message=str(test_result.get("message", "")),
    )


@router.get("/connect")
def google_calendar_connect(services: list[str] = Query(default=[])):
    """
    Initiate OAuth flow with selected services.

    Args:
        services: List of service names to request access for (e.g., ["gmail", "calendar"])
                 If empty, requests all services.
    """
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Add credentials to .env first.",
        )

    # Build scopes from selected services
    scopes = None
    if services:
        scopes = build_scopes_from_services(services)
        if not scopes:
            raise HTTPException(status_code=400, detail="No valid services selected")

    return RedirectResponse(url=get_authorization_url(scopes=scopes))


@router.get("/callback")
def google_calendar_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}?google_calendar=error&message={quote(error)}"
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    try:
        # Exchange code for credentials and save account
        credentials, account_id = exchange_code_for_credentials(code)
        print(f"Successfully connected account: {account_id}")
    except Exception as exc:
        print(f"Error in OAuth callback: {exc}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(
            url=f"{settings.frontend_url}?google_calendar=error&message={quote(str(exc))}"
        )

    return RedirectResponse(url=f"{settings.frontend_url}?google_calendar=connected")


@router.post("/disconnect")
def google_calendar_disconnect() -> dict[str, str]:
    clear_credentials()
    return {"status": "disconnected", "message": "Google Calendar token removed. Connect again to re-authorize."}


# Multi-account endpoints


@router.get("/accounts", response_model=AccountsListResponse)
async def get_accounts() -> AccountsListResponse:
    """Get all connected Google accounts."""
    await migrate_legacy_token_to_db()
    accounts = await list_accounts()

    account_infos = []
    for account in accounts:
        # Get granted services from scopes
        granted_services = []
        for scope in account.granted_scopes:
            service = get_service_from_scope(scope)
            if service and service not in granted_services:
                granted_services.append(service)

        account_infos.append(
            AccountInfo(
                id=account.id,
                email=account.email,
                account_label=account.account_label,
                granted_services=granted_services,
                is_primary=account.is_primary,
                created_at=account.created_at.isoformat() if account.created_at else None,
                updated_at=account.updated_at.isoformat() if account.updated_at else None,
            )
        )

    return AccountsListResponse(accounts=account_infos)


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str) -> dict[str, str]:
    """Delete a specific Google account."""
    success = await db_delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted", "message": "Account removed successfully"}


@router.post("/accounts/{account_id}/set-primary")
async def set_account_primary(account_id: str) -> AccountInfo:
    """Set an account as the primary account."""
    account = await set_primary_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Get granted services
    granted_services = []
    for scope in account.granted_scopes:
        service = get_service_from_scope(scope)
        if service and service not in granted_services:
            granted_services.append(service)

    return AccountInfo(
        id=account.id,
        email=account.email,
        account_label=account.account_label,
        granted_services=granted_services,
        is_primary=account.is_primary,
        created_at=account.created_at.isoformat() if account.created_at else None,
        updated_at=account.updated_at.isoformat() if account.updated_at else None,
    )


@router.patch("/accounts/{account_id}/label")
async def update_label(account_id: str, request: UpdateAccountLabelRequest) -> AccountInfo:
    """Update an account's label."""
    account = await update_account_label(account_id, request.label)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Get granted services
    granted_services = []
    for scope in account.granted_scopes:
        service = get_service_from_scope(scope)
        if service and service not in granted_services:
            granted_services.append(service)

    return AccountInfo(
        id=account.id,
        email=account.email,
        account_label=account.account_label,
        granted_services=granted_services,
        is_primary=account.is_primary,
        created_at=account.created_at.isoformat() if account.created_at else None,
        updated_at=account.updated_at.isoformat() if account.updated_at else None,
    )
