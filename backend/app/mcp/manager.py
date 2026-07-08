"""Robinhood MCP manager — tool discovery and execution."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.robinhood.mcp_client import RobinhoodMCPError, get_robinhood_mcp_client

logger = logging.getLogger(__name__)

_tools_cache: list[dict[str, Any]] | None = None


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


class RobinhoodMCPManager:
    async def is_connected(self) -> bool:
        client = await get_robinhood_mcp_client()
        return client is not None

    async def list_tools(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        global _tools_cache
        if _tools_cache is not None and not refresh:
            return _tools_cache

        client = await get_robinhood_mcp_client()
        if not client:
            return []

        try:
            tools = await client.list_tools()
            _tools_cache = tools
            return tools
        except RobinhoodMCPError as exc:
            logger.warning("Failed to list Robinhood MCP tools: %s", exc)
            return []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        client = await get_robinhood_mcp_client()
        if not client:
            raise RobinhoodMCPError("Robinhood is not connected. Connect from Stock Research first.")

        result = await client.call_tool(name, arguments or {})
        if isinstance(result, dict) and "content" in result:
            parts = []
            for item in result.get("content", []):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            if parts:
                return "\n".join(parts)
        return result

    def list_tools_sync(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        return _run_async(self.list_tools(refresh=refresh))

    def call_tool_sync(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return _run_async(self.call_tool(name, arguments))


_manager: RobinhoodMCPManager | None = None


def get_mcp_manager() -> RobinhoodMCPManager:
    global _manager
    if _manager is None:
        _manager = RobinhoodMCPManager()
    return _manager


def clear_tools_cache() -> None:
    global _tools_cache
    _tools_cache = None
