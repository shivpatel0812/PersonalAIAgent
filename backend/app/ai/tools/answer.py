"""Answer tool - allows the agent to provide a final response."""

from typing import Any
from pydantic import BaseModel

from app.ai.tools.base import Tool, ToolParameter


class AnswerResult(BaseModel):
    """Result of an answer action."""
    response: str


class AnswerTool(Tool):
    """Tool for providing a final answer to the user's question."""

    @property
    def name(self) -> str:
        return "answer"

    @property
    def description(self) -> str:
        return "provide your final answer when you have enough information"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "response",
                "type": "string",
                "description": "your full answer here, citing sources by URL when possible",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> AnswerResult:
        response = kwargs.get("response", "").strip()
        if not response:
            raise ValueError("Response parameter is required")
        return AnswerResult(response=response)
