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


def _normalize_image_entry(entry: Any) -> str | None:
    if isinstance(entry, str):
        cleaned = entry.strip().rstrip(",")
        return cleaned or None
    if isinstance(entry, dict):
        for key in ("url", "src", "image_url"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().rstrip(",")
    return None


_SKIP_IMAGE_MARKERS = (
    "logo",
    "icon",
    "favicon",
    "/nav",
    "navigation",
    "sprite",
    "appstore",
    "googleplay",
    "no-image",
)
_PRODUCT_IMAGE_MARKERS = (
    "product",
    "is/image",
    "cdn.shopify",
    "scene7",
    "/photos/",
    "/800x",
    "/600x",
    ".jpg",
    ".jpeg",
    ".webp",
    ".png",
)


def _score_image_url(url: str) -> int:
    lower = url.lower()
    if lower.endswith(".svg") or lower.endswith(".gif"):
        return -5
    for marker in _SKIP_IMAGE_MARKERS:
        if marker in lower:
            return -3
    score = 0
    for marker in _PRODUCT_IMAGE_MARKERS:
        if marker in lower:
            score += 2
    return score


def _verify_image_text(image_url: str, title: str, snippet: str) -> bool:
    """Mismatch-only verification — allow unless there's a clear category conflict."""
    url_lower = image_url.lower()
    title_lower = title.lower()

    # Category-level mismatch pairs: (url_terms, title_terms)
    mismatches = [
        (["food", "snack", "candy", "cookie", "chip", "fruit"], ["bottle", "electronics", "chair", "shoe"]),
        (["shoe", "sneaker", "boot"], ["bottle", "shirt", "food"]),
        (["shirt", "dress", "pants"], ["bottle", "electronics", "food"]),
    ]
    for url_terms, title_terms in mismatches:
        if any(t in url_lower for t in url_terms) and any(t in title_lower for t in title_terms):
            return False

    return True  # No mismatch detected — allow


def _verify_image_llm(image_url: str, title: str) -> bool:
    """Expensive LLM verification for ambiguous cases."""
    from app.ai.openai_client import chat_messages
    from app.ai.config import settings

    if not settings.openai_configured:
        return True  # Skip verification if no LLM available

    prompt = f"""Does this image URL seem relevant to this product?

Product: {title}
Image URL: {image_url}

Answer with just "yes" or "no". Consider:
- Does the URL path contain product-related terms?
- Are there obvious mismatches (e.g., food images for electronics)?
- Is this likely a product photo vs an ad/icon?"""

    try:
        response = chat_messages(
            [{"role": "user", "content": prompt}],
            max_tokens=10,
        ).strip().lower()
        return "yes" in response
    except Exception:
        return True  # On error, allow the image


# Thresholds
HIGH_CONFIDENCE_THRESHOLD = 4  # Amazon/Shopify CDN images score 4 easily
VERIFICATION_THRESHOLD = -1    # Allow more candidates through


def _pick_best_image_url(item: dict[str, Any], fallback_urls: list[str], title: str = "", snippet: str = "") -> str | None:
    candidates: list[str] = []
    for entry in item.get("images") or []:
        url = _normalize_image_entry(entry)
        if url and url not in candidates:
            candidates.append(url)

    for url in fallback_urls:
        if url not in candidates:
            candidates.append(url)

    if not candidates:
        return None

    ranked = sorted(candidates, key=_score_image_url, reverse=True)

    # Try top 3 candidates before falling back
    for candidate in ranked[:3]:
        score = _score_image_url(candidate)
        if score >= HIGH_CONFIDENCE_THRESHOLD:
            print(f"  ✓ Image: high confidence (score={score}), using directly")
            return candidate
        if score >= VERIFICATION_THRESHOLD and _verify_image_text(candidate, title, snippet):
            print(f"  ✓ Image: text verification passed (score={score})")
            return candidate

    # If all candidates failed text verification, return the highest-scored one
    # (only show placeholder for truly negative scores)
    if ranked and _score_image_url(ranked[0]) >= 0:
        print(f"  ⚠️  Image: no verification passed, using best candidate (score={_score_image_url(ranked[0])})")
        return ranked[0]

    print(f"  ✗ Image: all candidates negative score, showing placeholder")
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
        "search_depth": "advanced" if include_images else "basic",
        "max_results": max_results,
        "include_answer": False,
        "include_images": include_images,
    }

    response = httpx.post(TAVILY_SEARCH_URL, json=payload, timeout=45.0)
    response.raise_for_status()
    data = response.json()

    top_level_images = [
        url.strip().rstrip(",")
        for url in data.get("images") or []
        if isinstance(url, str) and url.strip()
    ]

    results: list[SearchResult] = []
    for index, item in enumerate(data.get("results", [])):
        title = item.get("title", "")
        snippet = item.get("content", "")
        fallbacks = [top_level_images[index]] if index < len(top_level_images) else []
        image_url = _pick_best_image_url(item, fallbacks, title, snippet)
        results.append(
            SearchResult(
                title=title,
                snippet=snippet,
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
