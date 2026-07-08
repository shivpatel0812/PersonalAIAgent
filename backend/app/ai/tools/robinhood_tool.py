"""Robinhood MCP tool proxies for the AI agent."""

from __future__ import annotations

import json
from typing import Any

from app.ai.tools.base import Tool, ToolParameter
from app.mcp.manager import get_mcp_manager
from app.robinhood.mcp_client import RobinhoodMCPError


class RobinhoodMCPTool(Tool):
    """Proxy a single Robinhood MCP tool into the agent registry."""

    def __init__(self, *, name: str, description: str, input_schema: dict[str, Any]):
        self._name = name
        self._description = description
        self._input_schema = input_schema

    @property
    def name(self) -> str:
        return f"robinhood_{self._name}"

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> list[ToolParameter]:
        properties = self._input_schema.get("properties", {})
        required = set(self._input_schema.get("required", []))
        params: list[ToolParameter] = []
        for key, schema in properties.items():
            params.append(
                {
                    "name": key,
                    "type": schema.get("type", "string"),
                    "description": schema.get("description", key),
                    "required": key in required,
                }
            )
        if not params:
            params.append(
                {
                    "name": "payload",
                    "type": "string",
                    "description": "Optional JSON arguments for the Robinhood MCP tool",
                    "required": False,
                }
            )
        return params

    def execute(self, **kwargs) -> Any:
        arguments = dict(kwargs)
        if "payload" in arguments and len(arguments) == 1:
            try:
                arguments = json.loads(arguments["payload"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
        try:
            return get_mcp_manager().call_tool_sync(self._name, arguments)
        except RobinhoodMCPError as exc:
            return {"error": str(exc)}


def get_robinhood_tools() -> list[Tool]:
    manager = get_mcp_manager()
    tools: list[Tool] = []
    for item in manager.list_tools_sync():
        name = item.get("name")
        if not name:
            continue
        tools.append(
            RobinhoodMCPTool(
                name=name,
                description=item.get("description") or f"Robinhood MCP tool: {name}",
                input_schema=item.get("inputSchema") or {},
            )
        )
    return tools
