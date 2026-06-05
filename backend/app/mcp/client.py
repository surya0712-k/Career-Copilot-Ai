import json
from typing import Any

import httpx

from app.config import get_settings


class MCPClient:
    """HTTP client for MCP research tools (calls MCP server REST endpoints or direct implementation)."""

    def __init__(self):
        self.settings = get_settings()

    async def web_search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        from app.mcp.server import _duckduckgo_search

        return await _duckduckgo_search(query, max_results)

    async def fetch_url(self, url: str) -> str:
        from app.mcp.server import _fetch_page_text

        return await _fetch_page_text(url)

    async def company_research(self, company: str, role: str, level: str = "internship") -> dict[str, Any]:
        from app.mcp.server import _duckduckgo_search

        queries = [
            f"{company} {role} {level} interview process",
            f"{company} {role} requirements skills",
            f"{company} {level} interview questions",
        ]
        search_results = []
        for q in queries:
            results = await _duckduckgo_search(q, max_results=3)
            search_results.extend(results)

        snippets = [r["title"] for r in search_results[:10]]
        return {
            "company": company,
            "role": role,
            "level": level,
            "search_results": search_results,
            "requirements_summary": (
                f"Research for {role} at {company} ({level}): " + "; ".join(snippets)
            ),
        }
