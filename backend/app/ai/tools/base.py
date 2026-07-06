"""
Tool registry system for the AI agent.

This module provides a base Tool class and ToolRegistry for dynamically
managing agent tools without hardcoded logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, TypedDict


class ToolParameter(TypedDict, total=False):
    """Defines a single parameter for a tool."""
    name: str
    type: str
    description: str
    required: bool


class Tool(ABC):
    """
    Base class for all agent tools.

    Each tool must define:
    - name: unique identifier used in JSON actions
    - description: what the tool does (shown to LLM)
    - parameters: list of parameters the tool accepts
    - execute: the function that runs when the tool is called
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this tool (e.g., 'search', 'scrape')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """List of parameters this tool accepts."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool with the given parameters.

        Args:
            **kwargs: Parameters as defined in self.parameters

        Returns:
            The result of executing the tool
        """
        pass

    def get_json_example(self) -> dict[str, Any]:
        """
        Generate a JSON example for the system prompt.

        Returns:
            A dict showing the expected JSON format for this tool
        """
        example: dict[str, Any] = {"action": self.name}
        for param in self.parameters:
            if param.get("required", True):
                example[param["name"]] = f"<{param['description']}>"
        return example

    def validate_parameters(self, provided: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate that required parameters are provided.

        Args:
            provided: Dictionary of provided parameters

        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.parameters:
            if param.get("required", True):
                if param["name"] not in provided or not provided[param["name"]]:
                    return False, f'Missing required parameter "{param["name"]}"'
        return True, None


class ToolRegistry:
    """
    Registry for managing agent tools.

    Allows dynamic registration and lookup of tools without hardcoded logic.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a new tool.

        Args:
            tool: The tool instance to register

        Raises:
            ValueError: If a tool with the same name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """
        Get a tool by name.

        Args:
            name: The tool name

        Returns:
            The tool instance or None if not found
        """
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_available_actions(self) -> list[str]:
        """Get list of all available action names."""
        return list(self._tools.keys())

    def generate_system_prompt(self, base_instructions: str = "") -> str:
        """
        Generate a system prompt dynamically from registered tools.

        Args:
            base_instructions: Optional base instructions to include

        Returns:
            Complete system prompt with tool descriptions and examples
        """
        if not self._tools:
            return base_instructions

        lines = []

        if base_instructions:
            lines.append(base_instructions)
            lines.append("")

        lines.append("You have the following tools available:")
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")

        lines.append("")
        lines.append("You must respond in one of these ways only, as valid JSON with no other text:")
        lines.append("")

        for tool in self._tools.values():
            lines.append(f"To use {tool.name}:")
            import json
            lines.append(json.dumps(tool.get_json_example(), indent=2))
            lines.append("")

        return "\n".join(lines)


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _global_registry


def register_tool(tool: Tool) -> None:
    """Register a tool in the global registry."""
    _global_registry.register(tool)
