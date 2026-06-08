import asyncio
import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    GAP_ANALYSIS_PROMPT,
    GITHUB_ANALYZE_PROMPT,
    RESUME_PARSE_PROMPT,
    ROADMAP_PROMPT,
)
from app.agents.state import AgentState
from app.config import get_settings
from app.memory.retriever import build_rag_context, format_rag_context
from app.memory.store import MemoryStore
from app.mcp.client import MCPClient
from app.observability.timing import timed_node
from app.services.github_client import GitHubClient
from app.services.llm import get_llm
from app.services.prompt_context import build_gap_llm_payload, build_roadmap_llm_payload
from app.services.readiness_score import finalize_readiness_score
from app.services.roadmap_utils import normalize_milestone_weeks

settings = get_settings()


class GapAnalysisOutput(BaseModel):
    critical_gaps: list[str] = Field(default_factory=list, max_length=5)
    nice_to_have_gaps: list[str] = Field(default_factory=list, max_length=3)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    recommendations: list[str] = Field(default_factory=list, max_length=5)
    readiness_score: float = Field(default=0.0, ge=0, le=10)


class RoadmapTaskOutput(BaseModel):
    title: str = Field(max_length=80)
    description: str = Field(default="", max_length=200)


class MilestoneOutput(BaseModel):
    title: str = Field(max_length=80)
    description: str = Field(default="", max_length=200)
    week_start: int = Field(default=1, ge=1, le=52)
    week_end: int = Field(default=2, ge=1, le=52)
    tasks: list[RoadmapTaskOutput] = Field(default_factory=list, max_length=3)
    success_criteria: str = Field(default="", max_length=200)


class RoadmapOutput(BaseModel):
    title: str = Field(max_length=100)
    milestones: list[MilestoneOutput] = Field(default_factory=list, max_length=4)


@timed_node("seed_resume")
async def seed_resume_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    """Use resume already parsed at upload — skip a redundant LLM call."""
    parsed = state.get("resume_parsed") or {}
    resume_text = state.get("resume_text", "")

    if parsed:
        skills = parsed.get("skills", [])
        summary = parsed.get("summary") or ""
        if not summary and skills:
            summary = f"Skills: {', '.join(skills[:20])}"
        return {
            "resume_analysis": {
                "summary": (summary or "Resume uploaded")[:800],
                "skills": skills[:20],
                "experience_count": len(parsed.get("experience", [])),
                "raw_text_length": len(resume_text),
            }
        }

    llm = get_llm()
    target = f"{state.get('target_company', '')} {state.get('target_role', '')}"
    response = await llm.ainvoke(
        [
            SystemMessage(content=RESUME_PARSE_PROMPT),
            HumanMessage(content=f"Target role: {target}\n\nResume:\n{resume_text[:10000]}"),
        ]
    )
    return {"resume_analysis": {"summary": response.content, "raw_text_length": len(resume_text)}}


@timed_node("parallel_fetch")
async def parallel_fetch_node(
    state: AgentState, db: AsyncSession, github_token: str | None = None
) -> dict[str, Any]:
    """Run GitHub analysis and role research concurrently."""
    github_result, research_result = await asyncio.gather(
        analyze_github_node(state, db, github_token),
        research_role_node(state, db),
    )
    return {**github_result, **research_result}


async def parse_resume_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    return await seed_resume_node(state, db)


@timed_node("analyze_github")
async def analyze_github_node(
    state: AgentState, db: AsyncSession, github_token: str | None = None
) -> dict[str, Any]:
    username = state.get("github_username", "")
    if not username:
        return {"github_analysis": {"error": "No GitHub username provided"}}

    client = GitHubClient(access_token=github_token)
    github_data = await client.analyze_profile(username)

    # Fast path: pass raw GitHub JSON to gap analysis — skip separate LLM summarization
    if settings.fast_onboarding:
        return {"github_analysis": github_data}

    llm = get_llm()
    target = f"{state.get('target_company', '')} {state.get('target_role', '')}"
    response = await llm.ainvoke(
        [
            SystemMessage(content=GITHUB_ANALYZE_PROMPT),
            HumanMessage(
                content=f"Target role: {target}\n\nGitHub data:\n{json.dumps(github_data, indent=2)[:4000]}"
            ),
        ]
    )
    github_data["analysis"] = response.content
    return {"github_analysis": github_data}


@timed_node("research_role")
async def research_role_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    company = state.get("target_company", "")
    role = state.get("target_role", "")
    level = state.get("level", "internship")

    if settings.fast_onboarding or settings.skip_web_research:
        return {
            "role_research": {
                "company": company,
                "role": role,
                "level": level,
                "requirements_summary": f"{role} at {company} ({level}) — standard technical interview expectations.",
                "search_results": [],
            }
        }

    mcp = MCPClient()
    research = await mcp.company_research(company, role, level)
    return {"role_research": research}


@timed_node("detect_gaps")
async def detect_gaps_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm().bind(max_tokens=settings.llm_onboarding_max_tokens)
    structured_llm = llm.with_structured_output(GapAnalysisOutput)

    target = f"{state.get('target_company')} {state.get('target_role')} ({state.get('level')})"
    payload = build_gap_llm_payload(
        resume_analysis=state.get("resume_analysis", {}),
        resume_text=state.get("resume_text") or "",
        github_analysis=state.get("github_analysis", {}),
        role_research=state.get("role_research", {}),
        target=target,
    )

    result: GapAnalysisOutput = await structured_llm.ainvoke(
        [
            SystemMessage(content=GAP_ANALYSIS_PROMPT),
            HumanMessage(content=payload),
        ]
    )
    gaps = result.model_dump()
    gaps["readiness_score"] = finalize_readiness_score(
        gaps,
        github_analysis=state.get("github_analysis"),
        resume_analysis=state.get("resume_analysis"),
        target=target,
    )
    return {"gap_analysis": gaps}


@timed_node("store_memory")
async def store_profile_memory_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    if settings.defer_memory_writes:
        return {"pending_memory_chunks": _collect_memory_chunks(state)}

    user_id = uuid.UUID(state["user_id"])
    goal_id = uuid.UUID(state["goal_id"]) if state.get("goal_id") else None
    chunks = _collect_memory_chunks(state)
    if chunks:
        store = MemoryStore(db)
        await store.store_chunks_parallel(user_id, chunks, goal_id=goal_id)
    return {}


def _collect_memory_chunks(state: AgentState) -> list[tuple[str, str, dict | None]]:
    chunks: list[tuple[str, str, dict | None]] = []
    if resume := state.get("resume_analysis"):
        chunks.append((f"Resume analysis: {resume.get('summary', '')[:1500]}", "resume_insight", None))
    if github := state.get("github_analysis"):
        summary = github.get("analysis") or json.dumps(
            {k: github.get(k) for k in ("username", "languages", "top_repos", "public_repos") if k in github}
        )[:1500]
        chunks.append((f"GitHub analysis: {summary}", "github_insight", None))
    if gaps := state.get("gap_analysis"):
        gap_text = (
            f"Gap analysis - Critical: {gaps.get('critical_gaps', [])}. "
            f"Strengths: {gaps.get('strengths', [])}. "
            f"Recommendations: {gaps.get('recommendations', [])}"
        )
        chunks.append((gap_text, "gap_finding", {"readiness_score": gaps.get("readiness_score")}))
    return chunks


async def retrieve_context_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    query = state.get("goal") or f"{state.get('target_company')} {state.get('target_role')}"
    memories = await build_rag_context(
        db, user_id, query, chunk_types=None, limit=10
    )
    return {"retrieved_memory": memories}


async def generate_roadmap_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm().bind(max_tokens=settings.llm_onboarding_max_tokens)
    structured_llm = llm.with_structured_output(RoadmapOutput)

    target = f"{state.get('target_company')} {state.get('target_role')} ({state.get('level')})"
    memory_context = await format_rag_context(state.get("retrieved_memory", []))
    payload = build_roadmap_llm_payload(
        gap_analysis=state.get("gap_analysis", {}),
        target=target,
        memory=memory_context,
    )

    result: RoadmapOutput = await structured_llm.ainvoke(
        [
            SystemMessage(content=ROADMAP_PROMPT),
            HumanMessage(content=payload),
        ]
    )
    roadmap = result.model_dump()
    for milestone in roadmap.get("milestones", []):
        for task in milestone.get("tasks", []):
            task.setdefault("resources", [])
    normalize_milestone_weeks(roadmap.get("milestones", []))
    return {"roadmap": roadmap}


async def store_roadmap_memory_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    roadmap = state.get("roadmap", {})
    if not roadmap:
        return {}

    store = MemoryStore(db)
    milestone_summaries = [
        f"Week {m.get('week_start')}-{m.get('week_end')}: {m.get('title')} - {m.get('description', '')}"
        for m in roadmap.get("milestones", [])
    ]
    content = f"Roadmap '{roadmap.get('title', '')}': " + "; ".join(milestone_summaries)
    await store.store_chunk(user_id, content, "roadmap_update", metadata={"roadmap": roadmap})
    return {}
