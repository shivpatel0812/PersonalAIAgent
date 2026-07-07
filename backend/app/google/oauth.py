from pathlib import Path
import asyncio
import concurrent.futures

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings
from app.db.google_accounts import (
    delete_account,
    get_account,
    get_primary_account,
    list_accounts,
    save_account,
    set_primary_account as db_set_primary_account,
    update_account_label,
)

# Scope groups organized by service
SCOPE_GROUPS = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar",
    ],
    "drive": [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
    ],
    "sheets": [
        "https://www.googleapis.com/auth/spreadsheets",
    ],
    "youtube": [
        "https://www.googleapis.com/auth/youtube.readonly",
    ],
}

# All scopes combined (for backward compatibility)
ALL_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/youtube.readonly",
]

TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / ".data" / "google_token.json"


def _run_async(coro):
    """Run async DB helpers from sync OAuth code paths."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def create_oauth_flow(scopes: list[str] | None = None) -> Flow:
    """
    Create OAuth flow with custom scopes.

    Args:
        scopes: List of scope URLs to request. If None, requests all scopes.
    """
    selected_scopes = scopes if scopes is not None else ALL_SCOPES
    return Flow.from_client_config(
        _client_config(),
        scopes=selected_scopes,
        redirect_uri=settings.google_redirect_uri,
    )


def save_credentials(credentials: Credentials) -> None:
    """Legacy function - saves to file. Use save_account_credentials instead."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(credentials.to_json())


def load_credentials(account_id: str | None = None) -> Credentials | None:
    """
    Load credentials for a specific account or the primary account.

    Args:
        account_id: Optional account ID. If None, loads primary account.

    Returns:
        Credentials object or None if not found
    """
    async def _load() -> Credentials | None:
        if account_id:
            account = await get_account(account_id)
        else:
            account = await get_primary_account()

        if not account:
            return load_credentials_from_file()

        credentials = account.to_credentials()

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                await save_account(
                    credentials,
                    account.email,
                    account.account_label,
                    account.is_primary,
                )
            except Exception:
                pass

        return credentials

    return _run_async(_load())


def load_credentials_from_file() -> Credentials | None:
    """Load credentials from legacy token file."""
    if not TOKEN_PATH.exists():
        return None

    credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            save_credentials(credentials)
        except Exception:
            pass

    return credentials


def has_stored_credentials() -> bool:
    if TOKEN_PATH.exists():
        return True

    try:
        accounts = _run_async(list_accounts())
        return len(accounts) > 0
    except Exception:
        return False


def _get_user_email(credentials: Credentials) -> str:
    """Resolve the Google account email using the lightest available API."""
    # Prefer OAuth userinfo (works without Gmail API enabled).
    try:
        oauth2_service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
        profile = oauth2_service.userinfo().get().execute()
        email = profile.get("email")
        if email:
            return email
    except Exception:
        pass

    try:
        gmail_service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = gmail_service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        if email:
            return email
    except Exception:
        pass

    try:
        drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = drive_service.about().get(fields="user").execute()
        email = about.get("user", {}).get("emailAddress")
        if email:
            return email
    except Exception:
        pass

    raise ValueError(
        "Connected to Google but could not read your account email. "
        "Enable the Google OAuth userinfo scopes or Gmail API, then try again."
    )


def get_authorization_url(scopes: list[str] | None = None) -> str:
    """
    Get OAuth authorization URL with custom scopes.

    Args:
        scopes: List of scope URLs to request. If None, requests all scopes.
    """
    flow = create_oauth_flow(scopes=scopes)
    authorization_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url


def exchange_code_for_credentials(code: str, scopes: list[str] | None = None) -> tuple[Credentials, str]:
    """
    Exchange OAuth code for credentials and save to database.

    Args:
        code: OAuth authorization code
        scopes: List of scope URLs that were requested

    Returns:
        Tuple of (credentials, account_id)
    """
    flow = create_oauth_flow(scopes=scopes)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    email = _get_user_email(credentials)

    async def _save() -> str:
        accounts = await list_accounts()
        is_primary = len(accounts) == 0
        account = await save_account(
            credentials,
            email,
            account_label=None,
            is_primary=is_primary,
        )
        return account.id

    account_id = _run_async(_save())
    save_credentials(credentials)
    return credentials, account_id


async def migrate_legacy_token_to_db() -> None:
    """Import a legacy file-based token into google_accounts when the table is empty."""
    try:
        accounts = await list_accounts()
        if accounts:
            return

        credentials = load_credentials_from_file()
        if not credentials:
            return

        email = _get_user_email(credentials)
        await save_account(credentials, email, account_label=None, is_primary=True)
    except Exception as exc:
        print(f"Legacy Google token migration failed: {exc}")


def clear_credentials() -> None:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()

    async def _clear() -> None:
        accounts = await list_accounts()
        for account in accounts:
            await delete_account(account.id)

    try:
        _run_async(_clear())
    except Exception as exc:
        print(f"Failed to clear Google accounts from database: {exc}")


def get_granted_scopes(account_id: str | None = None) -> list[str]:
    """
    Get list of scopes that have been granted for an account.

    Args:
        account_id: Optional account ID. If None, uses primary account.

    Returns:
        List of granted scope URLs, or empty list if not connected.
    """
    credentials = load_credentials(account_id)
    if credentials is None:
        return []
    return credentials.scopes or []


def build_scopes_from_services(services: list[str]) -> list[str]:
    """
    Build scope list from service names.

    Args:
        services: List of service names (e.g., ["gmail", "calendar"])

    Returns:
        Combined list of scope URLs for requested services
    """
    scopes = []
    for service in services:
        if service in SCOPE_GROUPS:
            scopes.extend(SCOPE_GROUPS[service])
    return scopes


def get_service_from_scope(scope_url: str) -> str | None:
    """
    Get service name from scope URL.

    Args:
        scope_url: Scope URL (e.g., "https://www.googleapis.com/auth/calendar")

    Returns:
        Service name (e.g., "calendar") or None if not found
    """
    for service, scopes in SCOPE_GROUPS.items():
        if scope_url in scopes:
            return service
    return None


def get_granted_services(account_id: str | None = None) -> list[str]:
    """
    Get list of services that have been granted access for an account.

    Args:
        account_id: Optional account ID. If None, uses primary account.

    Returns:
        List of service names (e.g., ["gmail", "calendar"])
    """
    granted_scopes = get_granted_scopes(account_id)
    services = set()
    for scope in granted_scopes:
        service = get_service_from_scope(scope)
        if service:
            services.add(service)
    return list(services)


# Account management functions


async def get_all_accounts():
    """Get all connected Google accounts."""
    return await list_accounts()


async def remove_account(account_id: str) -> bool:
    """Remove a Google account."""
    return await delete_account(account_id)


async def set_primary(account_id: str):
    """Set an account as primary."""
    return await db_set_primary_account(account_id)


async def rename_account(account_id: str, label: str | None):
    """Update an account's label."""
    return await update_account_label(account_id, label)


def test_calendar_access() -> dict[str, str | bool | int | None]:
    credentials = load_credentials()
    if credentials is None:
        return {
            "connected": False,
            "calendar_access": False,
            "gmail_access": False,
            "message": "Google services are not connected yet.",
        }

    result = {
        "connected": True,
        "calendar_access": False,
        "gmail_access": False,
        "drive_access": False,
    }

    # Test Calendar
    try:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        calendar = service.calendars().get(calendarId="primary").execute()
        events = (
            service.events()
            .list(calendarId="primary", maxResults=1, singleEvents=True, orderBy="startTime")
            .execute()
        )
        result["calendar_access"] = True
        result["calendar_summary"] = calendar.get("summary")
        result["upcoming_events_sample"] = len(events.get("items", []))
    except Exception:
        pass

    # Test Gmail
    try:
        gmail_service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = gmail_service.users().getProfile(userId='me').execute()
        result["gmail_access"] = True
        result["email_address"] = profile.get("emailAddress")
    except Exception:
        pass

    # Test Drive
    try:
        drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = drive_service.about().get(fields="user").execute()
        result["drive_access"] = True
        result["drive_user"] = about.get("user", {}).get("emailAddress")
    except Exception:
        pass

    # Build status message
    working = []
    if result["calendar_access"]:
        working.append("Calendar")
    if result["gmail_access"]:
        working.append("Gmail")
    if result["drive_access"]:
        working.append("Drive")

    if len(working) == 3:
        result["message"] = "Google Calendar, Gmail, and Drive connections are working."
    elif len(working) > 0:
        result["message"] = f"{', '.join(working)} working."
    else:
        result["message"] = "All Google services access failed."

    return result
