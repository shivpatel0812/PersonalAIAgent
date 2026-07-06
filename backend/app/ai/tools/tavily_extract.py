import httpx
from pydantic import BaseModel
from typing import Any

from app.ai.config import settings
from app.ai.tools.base import Tool, ToolParameter

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
MAX_CONTENT_CHARS = 8_000


class ExtractResult(BaseModel):
    url: str
    title: str
    content: str
    truncated: bool = False


def extract_url(url: str, query: str | None = None) -> ExtractResult:
    if not settings.tavily_configured:
        raise ValueError("Tavily API key is not configured")

    payload: dict = {
        "api_key": settings.tavily_api_key,
        "urls": [url],
        "extract_depth": "basic",
    }

    if query:
        payload["query"] = query
        payload["chunks_per_source"] = 3

    response = httpx.post(TAVILY_EXTRACT_URL, json=payload, timeout=60.0)
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])
    if not results:
        failed = data.get("failed_results", [])
        detail = failed[0].get("error", "No content extracted") if failed else "No content extracted"
        raise ValueError(detail)

    item = results[0]
    raw_content = item.get("raw_content", "") or ""
    truncated = len(raw_content) > MAX_CONTENT_CHARS
    content = raw_content[:MAX_CONTENT_CHARS]

    if truncated:
        content += "\n\n[Content truncated for length.]"

    return ExtractResult(
        url=item.get("url", url),
        title=item.get("title", url),
        content=content,
        truncated=truncated,
    )


class ExtractUrlTool(Tool):
    """Tool for extracting full page content from a URL."""

    def __init__(self, context_query: str | None = None):
        """
        Initialize the extract URL tool.

        Args:
            context_query: Optional query to focus content extraction
        """
        self._context_query = context_query

    @property
    def name(self) -> str:
        return "scrape"

    @property
    def description(self) -> str:
        return "reads the full page content from a specific URL (use after search when snippets are not enough)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "url",
                "type": "string",
                "description": "https://the-url-to-read.com",
                "required": True,
            }
        ]

    def execute(self, **kwargs) -> ExtractResult:
        url = kwargs.get("url", "").strip()
        if not url:
            raise ValueError("URL parameter is required")
        return extract_url(url, query=self._context_query)
