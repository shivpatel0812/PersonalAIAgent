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
    image_url: str | None = None


def _first_image_url(item: dict[str, Any]) -> str | None:
    images = item.get("images") or []
    if not images:
        return None
    first = images[0]
    if isinstance(first, str) and first.strip():
        return first.strip()
    if isinstance(first, dict):
        for key in ("url", "src", "image_url"):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def web_search(
    query: str,
    max_results: int = 5,
    *,
    include_images: bool = False,
) -> list[SearchResult]:
    if not settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_images": include_images,
    }

    response = httpx.post(TAVILY_SEARCH_URL, json=payload, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    top_level_images = [
        url.strip()
        for url in data.get("images") or []
        if isinstance(url, str) and url.strip()
    ]

    results: list[SearchResult] = []
    for index, item in enumerate(data.get("results", [])):
        image_url = _first_image_url(item)
        if not image_url and index < len(top_level_images):
            image_url = top_level_images[index]
        results.append(
            SearchResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
                image_url=image_url,
            )
        )
    return results


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
