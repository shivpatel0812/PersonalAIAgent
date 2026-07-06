from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

SCOPES = [
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


def create_oauth_flow() -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


def save_credentials(credentials: Credentials) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(credentials.to_json())


def load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None

    # Use scopes stored in the token file so refresh works before re-auth adds Gmail scopes.
    credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            save_credentials(credentials)
        except Exception:
            pass

    return credentials


def has_stored_credentials() -> bool:
    return TOKEN_PATH.exists()


def get_authorization_url() -> str:
    flow = create_oauth_flow()
    authorization_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url


def exchange_code_for_credentials(code: str) -> Credentials:
    flow = create_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    save_credentials(credentials)
    return credentials


def clear_credentials() -> None:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()


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
