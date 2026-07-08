from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import settings
from app.db.robinhood_connections import delete_connection
from app.mcp.manager import clear_tools_cache, get_mcp_manager
from app.robinhood.oauth import (
    exchange_code_for_tokens,
    get_authorization_url,
    has_stored_credentials,
)

router = APIRouter(prefix="/auth/robinhood", tags=["robinhood-auth"])

MCP_URL = "https://agent.robinhood.com/mcp/trading"


class RobinhoodStatus(BaseModel):
    configured: bool
    connected: bool
    mcp_url: str
    connect_url: str | None = None
    message: str
    tools: list[str] = []


class RobinhoodToolsResponse(BaseModel):
    tools: list[dict]


@router.get("/status", response_model=RobinhoodStatus)
async def robinhood_status() -> RobinhoodStatus:
    connected = await has_stored_credentials()
    tools: list[str] = []
    if connected:
        tool_defs = await get_mcp_manager().list_tools()
        tools = [tool.get("name", "") for tool in tool_defs if tool.get("name")]

    if not connected:
        return RobinhoodStatus(
            configured=True,
            connected=False,
            mcp_url=MCP_URL,
            connect_url="/auth/robinhood/connect",
            message="Connect Robinhood Agentic Trading to read portfolio data and trade in your Agentic account.",
            tools=[],
        )

    return RobinhoodStatus(
        configured=True,
        connected=True,
        mcp_url=MCP_URL,
        connect_url="/auth/robinhood/connect",
        message="Robinhood MCP connected. Stock Research chat can use your portfolio tools.",
        tools=tools,
    )


@router.get("/connect")
async def robinhood_connect():
    try:
        url = await get_authorization_url()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url=url)


@router.get("/callback")
async def robinhood_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(
            url=f"{settings.frontend_url}?robinhood=error&message={quote(error)}"
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    try:
        await exchange_code_for_tokens(code, state)
        clear_tools_cache()
    except Exception as exc:
        return RedirectResponse(
            url=f"{settings.frontend_url}?robinhood=error&message={quote(str(exc))}"
        )
    return RedirectResponse(url=f"{settings.frontend_url}?robinhood=connected&page=stocks")


@router.post("/disconnect")
async def robinhood_disconnect() -> dict[str, str]:
    await delete_connection()
    clear_tools_cache()
    return {"status": "disconnected"}


@router.get("/tools", response_model=RobinhoodToolsResponse)
async def robinhood_tools() -> RobinhoodToolsResponse:
    if not await has_stored_credentials():
        raise HTTPException(status_code=400, detail="Robinhood is not connected")
    tools = await get_mcp_manager().list_tools(refresh=True)
    return RobinhoodToolsResponse(tools=tools)
