import json
import re
from typing import Any
from urllib.parse import quote_plus

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("career-research", host="0.0.0.0", port=8080)


async def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "CareerCopilot/1.0"})
        resp.raise_for_status()
        html = resp.text

    results = []
    for match in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
        html,
    ):
        href, title = match.group(1), match.group(2).strip()
        if href.startswith("//"):
            href = "https:" + href
        results.append({"title": title, "url": href, "snippet": ""})
        if len(results) >= max_results:
            break
    return results


async def _fetch_page_text(url: str, max_chars: int = 8000) -> str:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "CareerCopilot/1.0"})
        resp.raise_for_status()
        text = resp.text
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information about companies, roles, interview processes, and career advice."""
    results = await _duckduckgo_search(query, max_results)
    return json.dumps(results, indent=2)


@mcp.tool()
async def fetch_url(url: str) -> str:
    """Fetch and extract text content from a URL."""
    try:
        content = await _fetch_page_text(url)
        return content or "No content extracted."
    except Exception as e:
        return f"Error fetching URL: {e}"


@mcp.tool()
async def company_research(company: str, role: str, level: str = "internship") -> str:
    """Research a company's interview process, role requirements, and culture for a specific position."""
    queries = [
        f"{company} {role} {level} interview process",
        f"{company} {role} requirements skills",
        f"{company} {level} interview questions software engineer",
    ]

    all_results: dict[str, Any] = {
        "company": company,
        "role": role,
        "level": level,
        "search_results": [],
        "requirements_summary": "",
    }

    for q in queries:
        results = await _duckduckgo_search(q, max_results=3)
        all_results["search_results"].extend(results)

    snippets = [r["title"] for r in all_results["search_results"][:10]]
    all_results["requirements_summary"] = (
        f"Research findings for {role} at {company} ({level}): "
        + "; ".join(snippets)
    )

    return json.dumps(all_results, indent=2)


if __name__ == "__main__":
    mcp.run(transport="sse")
