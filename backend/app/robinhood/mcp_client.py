"""HTTP client for Robinhood's remote Trading MCP server."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.robinhood.oauth import refresh_access_token_if_needed

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "personal-ai-agent"
_CLIENT_VERSION = "0.1.0"


class RobinhoodMCPError(RuntimeError):
    pass


class RobinhoodMCPClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.robinhood_mcp_url.rstrip("/")
        self._session_id: str | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)

        if response.headers.get("mcp-session-id"):
            self._session_id = response.headers["mcp-session-id"]

        if response.status_code == 401:
            raise RobinhoodMCPError("Robinhood MCP authentication failed. Reconnect your account.")

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(response.text)

        if response.status_code >= 400:
            raise RobinhoodMCPError(response.text or f"MCP request failed ({response.status_code})")

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise RobinhoodMCPError(response.text or "Invalid MCP response") from exc

        if "error" in data:
            raise RobinhoodMCPError(str(data["error"]))
        return data.get("result", data)

    @staticmethod
    def _parse_sse(body: str) -> dict[str, Any]:
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            data = json.loads(payload)
            if "result" in data:
                return data["result"]
            if "error" in data:
                raise RobinhoodMCPError(str(data["error"]))
        raise RobinhoodMCPError("Empty MCP SSE response")

    async def initialize(self) -> dict[str, Any]:
        return await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": _PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": _CLIENT_NAME, "version": _CLIENT_VERSION},
                },
            }
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.initialize()
        result = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
        )
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        await self.initialize()
        result = await self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        return result


async def get_robinhood_mcp_client() -> RobinhoodMCPClient | None:
    token = await refresh_access_token_if_needed()
    if not token:
        return None
    return RobinhoodMCPClient(token)
