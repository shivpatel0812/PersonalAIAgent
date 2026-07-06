import httpx
from pydantic import BaseModel
from typing import Any

from app.ai.config import settings
from app.ai.tools.base import Tool, ToolParameter

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class SearchResult(BaseModel):
    title: str
    snippet: str
    url: str


def web_search(query: str, max_results: int = 5) -> list[SearchResult]:
    if not settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }

    response = httpx.post(TAVILY_SEARCH_URL, json=payload, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    return [
        SearchResult(
            title=item.get("title", ""),
            snippet=item.get("content", ""),
            url=item.get("url", ""),
        )
        for item in data.get("results", [])
    ]


class WebSearchTool(Tool):
    """Tool for searching the internet using Tavily."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return "searches the internet and returns titles, short snippets, and URLs"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "query",
                "type": "string",
                "description": "the search query you want to run",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> list[SearchResult]:
        query = kwargs.get("query", "").strip()
        if not query:
            raise ValueError("Query parameter is required")
        return web_search(query)
