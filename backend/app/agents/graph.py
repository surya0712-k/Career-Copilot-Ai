import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.timing import timed_step

from app.agents.nodes.interview import decide_next_node
from app.agents.nodes.profile import (
    detect_gaps_node,
    parallel_fetch_node,
    seed_resume_node,
    store_profile_memory_node,
)
from app.agents.nodes.progress import load_progress_node, merge_completed_node
from app.agents.state import AgentState
from app.services.career.roadmap import RoadmapService


def _wrap(fn, db: AsyncSession, **kwargs):
    async def node(state: AgentState) -> dict[str, Any]:
        return await fn(state, db, **kwargs)

    return node


async def _generate_roadmap_v2_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    service = RoadmapService()
    goal_id = uuid.UUID(state["goal_id"]) if state.get("goal_id") else None
    user_id = uuid.UUID(state["user_id"])
    if goal_id is None:
        return {}
    profile_gaps = state.get("gap_analysis", {})
    roadmap_data = await service.generate_initial(
        db,
        user_id,
        goal_id,
        state.get("target_company", ""),
        state.get("target_role", ""),
        state.get("level", "internship"),
        profile_gaps,
    )
    return {"roadmap": roadmap_data}


async def _store_roadmap_v2_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    service = RoadmapService()
    roadmap_data = state.get("roadmap", {})
    if not roadmap_data:
        return {}
    goal_id = uuid.UUID(state["goal_id"])
    user_id = uuid.UUID(state["user_id"])
    await service.persist_roadmap(db, user_id, goal_id, roadmap_data)
    return {}


def build_profile_graph(db: AsyncSession, github_token: str | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("seed_resume", _wrap(seed_resume_node, db))
    graph.add_node("fetch_profile", _wrap(parallel_fetch_node, db, github_token=github_token))
    graph.add_node("detect_gaps", _wrap(detect_gaps_node, db))
    graph.add_node("store_memory", _wrap(store_profile_memory_node, db))

    graph.set_entry_point("seed_resume")
    graph.add_edge("seed_resume", "fetch_profile")
    graph.add_edge("fetch_profile", "detect_gaps")
    graph.add_edge("detect_gaps", "store_memory")
    graph.add_edge("store_memory", END)

    return graph.compile()


def build_roadmap_graph(db: AsyncSession):
    graph = StateGraph(AgentState)
    graph.add_node("generate_roadmap", _wrap(_generate_roadmap_v2_node, db))

    graph.set_entry_point("generate_roadmap")
    graph.add_edge("generate_roadmap", END)

    return graph.compile()


def build_recalc_roadmap_graph(db: AsyncSession):
    graph = StateGraph(AgentState)
    graph.add_node("load_progress", _wrap(load_progress_node, db))
    graph.add_node("generate_roadmap", _wrap(_generate_roadmap_v2_node, db))
    graph.add_node("merge_completed", _wrap(merge_completed_node, db))

    graph.set_entry_point("load_progress")
    graph.add_edge("load_progress", "generate_roadmap")
    graph.add_edge("generate_roadmap", "merge_completed")
    graph.add_edge("merge_completed", END)

    return graph.compile()


def build_interview_graph(db: AsyncSession):
    graph = StateGraph(AgentState)
    graph.set_entry_point("load_context")
    return graph.compile()


async def run_profile_phase(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_data: dict[str, Any],
    resume_text: str,
    github_username: str,
    github_token: str | None = None,
    resume_parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initial_state: AgentState = {
        "user_id": str(user_id),
        "goal_id": str(goal_data.get("id", "")),
        "goal": f"{goal_data['target_company']} {goal_data['target_role']}",
        "target_company": goal_data["target_company"],
        "target_role": goal_data["target_role"],
        "level": goal_data.get("level", "internship"),
        "resume_text": resume_text,
        "resume_parsed": resume_parsed or {},
        "github_username": github_username,
    }
    profile_graph = build_profile_graph(db, github_token)
    async with timed_step(None, "profile_graph"):
        return await profile_graph.ainvoke(initial_state)


async def run_roadmap_phase(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_data: dict[str, Any],
    resume_text: str,
    github_username: str,
    profile_result: dict[str, Any],
    resume_parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initial_state: AgentState = {
        "user_id": str(user_id),
        "goal_id": str(goal_data.get("id", "")),
        "goal": f"{goal_data['target_company']} {goal_data['target_role']}",
        "target_company": goal_data["target_company"],
        "target_role": goal_data["target_role"],
        "level": goal_data.get("level", "internship"),
        "resume_text": resume_text,
        "resume_parsed": resume_parsed or {},
        "github_username": github_username,
    }
    merged_state = {**initial_state, **profile_result}
    roadmap_graph = build_roadmap_graph(db)
    async with timed_step(None, "roadmap_graph"):
        return await roadmap_graph.ainvoke(merged_state)


async def run_full_onboarding(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_data: dict[str, Any],
    resume_text: str,
    github_username: str,
    github_token: str | None = None,
    resume_parsed: dict[str, Any] | None = None,
    on_step: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    async def step(label: str) -> None:
        if on_step:
            await on_step(label)

    await step("profile")
    profile_result = await run_profile_phase(
        db, user_id, goal_data, resume_text, github_username, github_token, resume_parsed
    )

    await step("roadmap")
    roadmap_result = await run_roadmap_phase(
        db, user_id, goal_data, resume_text, github_username, profile_result, resume_parsed
    )

    return {**profile_result, **roadmap_result}
