"""DuckDuckGo web search tool registered as 'web_search'."""

import asyncio
from typing import Any, Dict, List
import structlog

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None  # type: ignore

from app.tools.registry import register_tool

logger = structlog.get_logger(__name__)


def _sync_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Execute synchronous DuckDuckGo search."""
    if DDGS is None:
        raise RuntimeError("duckduckgo-search package is not installed.")
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
        return results


@register_tool(
    name="web_search",
    description="Search the web using DuckDuckGo to obtain relevant search results and links.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query string.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results to return (default: 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)
async def web_search(query: str, max_results: int = 5) -> str:
    """Execute web search asynchronously and format results."""
    try:
        results = await asyncio.to_thread(_sync_search, query, max_results)
        if not results:
            return f"No results found for query: '{query}'."

        formatted_parts: List[str] = []
        for idx, item in enumerate(results, start=1):
            title = item.get("title", "No Title")
            href = item.get("href", item.get("link", ""))
            body = item.get("body", item.get("snippet", ""))
            formatted_parts.append(
                f"{idx}. {title}\n   URL: {href}\n   Snippet: {body}"
            )

        return "\n\n".join(formatted_parts)
    except Exception as exc:
        logger.warning("Web search failed", query=query, error=str(exc))
        return f"Web search error: {str(exc)}"
