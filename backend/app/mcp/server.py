import json
import re
import uuid
from typing import Any
from urllib.parse import quote_plus

import httpx
from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.memory.qdrant_client import ensure_collection
from app.models import Goal, Profile, User
from app.services.career.github import GitHubAnalysisService
from app.services.career.interview import InterviewService
from app.services.career.memory import MemoryService
from app.services.career.roadmap import RoadmapService

settings = get_settings()
mcp = FastMCP("career-copilot", host="0.0.0.0", port=8080)


async def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
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
        f"Research findings for {role} at {company} ({level}): " + "; ".join(snippets)
    )

    return json.dumps(all_results, indent=2)


@mcp.tool()
async def analyze_github(user_id: str, target_company: str = "", target_role: str = "") -> str:
    """Analyze a user's GitHub profile for career coaching."""
    await ensure_collection()
    async with AsyncSessionLocal() as db:
        user = await db.get(User, uuid.UUID(user_id))
        if not user:
            return json.dumps({"error": "User not found"})
        goal_result = await db.execute(
            select(Goal).where(Goal.user_id == user.id, Goal.is_active.is_(True)).limit(1)
        )
        goal = goal_result.scalar_one_or_none()
        company = target_company or (goal.target_company if goal else "")
        role = target_role or (goal.target_role if goal else "Software Engineer")
        service = GitHubAnalysisService()
        result = await service.analyze(
            db, user.id, user.github_username, company, role, user.github_access_token
        )
        profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.github_data = result
            await db.commit()
        return json.dumps(result, indent=2)


@mcp.tool()
async def generate_roadmap(user_id: str, goal_id: str, recalculate: bool = False) -> str:
    """Generate or recalculate a career roadmap for a user goal."""
    await ensure_collection()
    async with AsyncSessionLocal() as db:
        uid = uuid.UUID(user_id)
        gid = uuid.UUID(goal_id)
        goal = await db.get(Goal, gid)
        if not goal or goal.user_id != uid:
            return json.dumps({"error": "Goal not found"})
        profile_result = await db.execute(select(Profile).where(Profile.user_id == uid))
        profile = profile_result.scalar_one_or_none()
        gap_analysis = profile.gap_analysis if profile else {}
        service = RoadmapService()
        if recalculate:
            from app.models import Roadmap

            rm_result = await db.execute(
                select(Roadmap)
                .where(Roadmap.goal_id == gid, Roadmap.user_id == uid, Roadmap.status == "active")
                .order_by(Roadmap.created_at.desc())
                .limit(1)
            )
            roadmap = rm_result.scalar_one_or_none()
            if not roadmap:
                return json.dumps({"error": "No active roadmap to recalculate"})
            new_roadmap = await service.recalculate(db, uid, roadmap.id)
            await db.commit()
            return json.dumps({"roadmap_id": str(new_roadmap.id), "title": new_roadmap.title, "version": new_roadmap.version})
        roadmap_data = await service.generate_initial(
            db, uid, gid, goal.target_company, goal.target_role, goal.level, gap_analysis or {}
        )
        roadmap = await service.persist_roadmap(db, uid, gid, roadmap_data)
        await db.commit()
        return json.dumps({"roadmap_id": str(roadmap.id), "title": roadmap.title, "milestones": len(roadmap_data.get("milestones", []))})


@mcp.tool()
async def generate_interview(user_id: str, goal_id: str, turn_number: int = 1) -> str:
    """Generate a mock interview question for a user."""
    await ensure_collection()
    async with AsyncSessionLocal() as db:
        uid = uuid.UUID(user_id)
        gid = uuid.UUID(goal_id)
        goal = await db.get(Goal, gid)
        if not goal or goal.user_id != uid:
            return json.dumps({"error": "Goal not found"})
        service = InterviewService()
        ctx = await service.load_context(
            db, uid, f"{goal.target_company} {goal.target_role}", gid
        )
        question = await service.generate_question(
            db, goal.target_company, goal.target_role, goal.level, ctx["rag_context"], turn_number
        )
        return json.dumps({"question": question, "turn_number": turn_number})


@mcp.tool()
async def save_memory(
    user_id: str,
    content: str,
    chunk_type: str,
    goal_id: str | None = None,
    metadata: str | None = None,
) -> str:
    """Save a memory chunk to the user's Second Brain."""
    await ensure_collection()
    async with AsyncSessionLocal() as db:
        meta = json.loads(metadata) if metadata else None
        gid = uuid.UUID(goal_id) if goal_id else None
        service = MemoryService()
        result = await service.save(db, uuid.UUID(user_id), content, chunk_type, gid, meta)
        await db.commit()
        return json.dumps(result)


@mcp.tool()
async def retrieve_memory(
    user_id: str,
    query: str,
    chunk_types: str | None = None,
    limit: int = 8,
) -> str:
    """Retrieve relevant memories from the user's Second Brain."""
    await ensure_collection()
    types = [t.strip() for t in chunk_types.split(",")] if chunk_types else None
    async with AsyncSessionLocal() as db:
        service = MemoryService()
        hits = await service.retrieve(db, uuid.UUID(user_id), query, types, None, limit)
        return json.dumps(hits, indent=2)


if __name__ == "__main__":
    mcp.run(transport="sse")
