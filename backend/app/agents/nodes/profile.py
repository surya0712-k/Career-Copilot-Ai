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
from app.memory.retriever import build_rag_context, format_rag_context
from app.memory.store import MemoryStore
from app.mcp.client import MCPClient
from app.services.github_client import GitHubClient
from app.services.llm import get_llm


class GapAnalysisOutput(BaseModel):
    critical_gaps: list[str] = Field(default_factory=list)
    nice_to_have_gaps: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    readiness_score: float = Field(default=0.0, ge=0, le=10)


class MilestoneTask(BaseModel):
    title: str
    description: str = ""
    resources: list[str] = Field(default_factory=list)


class MilestoneOutput(BaseModel):
    title: str
    description: str = ""
    week_start: int = 1
    week_end: int = 2
    tasks: list[MilestoneTask] = Field(default_factory=list)
    success_criteria: str = ""


class RoadmapOutput(BaseModel):
    title: str
    milestones: list[MilestoneOutput] = Field(default_factory=list)


async def parse_resume_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    resume_text = state.get("resume_text", "")
    target = f"{state.get('target_company', '')} {state.get('target_role', '')}"

    response = await llm.ainvoke(
        [
            SystemMessage(content=RESUME_PARSE_PROMPT),
            HumanMessage(
                content=f"Target role: {target}\n\nResume:\n{resume_text[:10000]}"
            ),
        ]
    )
    analysis = {"summary": response.content, "raw_text_length": len(resume_text)}
    return {"resume_analysis": analysis}


async def analyze_github_node(
    state: AgentState, db: AsyncSession, github_token: str | None = None
) -> dict[str, Any]:
    username = state.get("github_username", "")
    if not username:
        return {"github_analysis": {"error": "No GitHub username provided"}}

    client = GitHubClient(access_token=github_token)
    github_data = await client.analyze_profile(username)

    llm = get_llm()
    target = f"{state.get('target_company', '')} {state.get('target_role', '')}"
    response = await llm.ainvoke(
        [
            SystemMessage(content=GITHUB_ANALYZE_PROMPT),
            HumanMessage(
                content=f"Target role: {target}\n\nGitHub data:\n{json.dumps(github_data, indent=2)[:8000]}"
            ),
        ]
    )
    github_data["analysis"] = response.content
    return {"github_analysis": github_data}


async def research_role_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    company = state.get("target_company", "")
    role = state.get("target_role", "")
    level = state.get("level", "internship")

    mcp = MCPClient()
    research = await mcp.company_research(company, role, level)
    return {"role_research": research}


async def detect_gaps_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    structured_llm = llm.with_structured_output(GapAnalysisOutput)

    context = {
        "resume_analysis": state.get("resume_analysis", {}),
        "github_analysis": state.get("github_analysis", {}),
        "role_research": state.get("role_research", {}),
        "target": f"{state.get('target_company')} {state.get('target_role')} ({state.get('level')})",
    }

    result: GapAnalysisOutput = await structured_llm.ainvoke(
        [
            SystemMessage(content=GAP_ANALYSIS_PROMPT),
            HumanMessage(content=json.dumps(context, indent=2)[:12000]),
        ]
    )
    return {"gap_analysis": result.model_dump()}


async def store_profile_memory_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    store = MemoryStore(db)
    chunks: list[tuple[str, str, dict | None]] = []

    if resume := state.get("resume_analysis"):
        chunks.append((f"Resume analysis: {resume.get('summary', '')}", "resume_insight", None))
    if github := state.get("github_analysis"):
        chunks.append((f"GitHub analysis: {github.get('analysis', '')}", "github_insight", None))
    if gaps := state.get("gap_analysis"):
        gap_text = (
            f"Gap analysis - Critical: {gaps.get('critical_gaps', [])}. "
            f"Strengths: {gaps.get('strengths', [])}. "
            f"Recommendations: {gaps.get('recommendations', [])}"
        )
        chunks.append((gap_text, "gap_finding", {"readiness_score": gaps.get("readiness_score")}))

    if chunks:
        await store.store_chunks(user_id, chunks)
    return {}


async def retrieve_context_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    query = state.get("goal") or f"{state.get('target_company')} {state.get('target_role')}"
    memories = await build_rag_context(
        db, user_id, query, chunk_types=None, limit=10
    )
    return {"retrieved_memory": memories}


async def generate_roadmap_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    structured_llm = llm.with_structured_output(RoadmapOutput)

    memory_context = await format_rag_context(state.get("retrieved_memory", []))
    context = {
        "gap_analysis": state.get("gap_analysis", {}),
        "role_research": state.get("role_research", {}),
        "memory": memory_context,
        "target": f"{state.get('target_company')} {state.get('target_role')} ({state.get('level')})",
    }

    result: RoadmapOutput = await structured_llm.ainvoke(
        [
            SystemMessage(content=ROADMAP_PROMPT),
            HumanMessage(content=json.dumps(context, indent=2)[:12000]),
        ]
    )
    return {"roadmap": result.model_dump()}


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
