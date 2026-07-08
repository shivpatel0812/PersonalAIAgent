from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.db.microsoft_accounts import (
    delete_account as db_delete_account,
    list_accounts,
    set_primary_account,
    update_account_label,
)
from app.microsoft.oauth import (
    exchange_code_for_credentials,
    get_authorization_url,
    has_stored_credentials,
)

router = APIRouter(prefix="/auth/microsoft", tags=["microsoft-auth"])


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


class MicrosoftStatus(BaseModel):
    configured: bool
    connected: bool
    connect_url: str | None = None
    message: str


class UpdateAccountLabelRequest(BaseModel):
    label: str | None


@router.get("/status", response_model=MicrosoftStatus)
def microsoft_status() -> MicrosoftStatus:
    configured = settings.microsoft_oauth_configured
    connected = configured and has_stored_credentials()
    if not configured:
        return MicrosoftStatus(
            configured=False,
            connected=False,
            message="Add MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET to .env",
        )
    if not connected:
        return MicrosoftStatus(
            configured=True,
            connected=False,
            connect_url="/auth/microsoft/connect",
            message="Connect your Microsoft / Outlook account.",
        )
    return MicrosoftStatus(
        configured=True,
        connected=True,
        connect_url="/auth/microsoft/connect",
        message="Outlook connected.",
    )


@router.get("/connect")
def microsoft_connect(select_account: bool = Query(default=False)):
    if not settings.microsoft_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="Microsoft OAuth is not configured. Add credentials to .env first.",
        )
    return RedirectResponse(url=get_authorization_url(select_account=select_account))


@router.get("/callback")
def microsoft_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}?microsoft=error&message={quote(error)}"
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")
    try:
        exchange_code_for_credentials(code)
    except Exception as exc:
        return RedirectResponse(
            url=f"{settings.frontend_url}?microsoft=error&message={quote(str(exc))}"
        )
    return RedirectResponse(url=f"{settings.frontend_url}?microsoft=connected")


@router.get("/accounts", response_model=AccountsListResponse)
async def get_accounts() -> AccountsListResponse:
    accounts = await list_accounts()
    return AccountsListResponse(
        accounts=[
            AccountInfo(
                id=account.id,
                email=account.email,
                account_label=account.account_label,
                granted_services=["mail"],
                is_primary=account.is_primary,
                created_at=account.created_at.isoformat() if account.created_at else None,
                updated_at=account.updated_at.isoformat() if account.updated_at else None,
            )
            for account in accounts
        ]
    )


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str) -> dict[str, str]:
    success = await db_delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted", "message": "Microsoft account removed successfully"}


@router.post("/accounts/{account_id}/set-primary")
async def set_account_primary(account_id: str) -> AccountInfo:
    account = await set_primary_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountInfo(
        id=account.id,
        email=account.email,
        account_label=account.account_label,
        granted_services=["mail"],
        is_primary=account.is_primary,
        created_at=account.created_at.isoformat() if account.created_at else None,
        updated_at=account.updated_at.isoformat() if account.updated_at else None,
    )


@router.patch("/accounts/{account_id}/label")
async def update_label(account_id: str, request: UpdateAccountLabelRequest) -> AccountInfo:
    account = await update_account_label(account_id, request.label)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountInfo(
        id=account.id,
        email=account.email,
        account_label=account.account_label,
        granted_services=["mail"],
        is_primary=account.is_primary,
        created_at=account.created_at.isoformat() if account.created_at else None,
        updated_at=account.updated_at.isoformat() if account.updated_at else None,
    )
