import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.interview import (
    decide_next_node,
    evaluate_answer_node,
    generate_question_node,
    load_interview_context_node,
    summarize_session_node,
)
from app.agents.nodes.profile import (
    analyze_github_node,
    detect_gaps_node,
    generate_roadmap_node,
    parse_resume_node,
    research_role_node,
    retrieve_context_node,
    store_profile_memory_node,
    store_roadmap_memory_node,
)
from app.agents.state import AgentState


def _wrap(fn, db: AsyncSession, **kwargs):
    async def node(state: AgentState) -> dict[str, Any]:
        return await fn(state, db, **kwargs)

    return node


def build_profile_graph(db: AsyncSession, github_token: str | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("parse_resume", _wrap(parse_resume_node, db))
    graph.add_node("analyze_github", _wrap(analyze_github_node, db, github_token=github_token))
    graph.add_node("research_role", _wrap(research_role_node, db))
    graph.add_node("detect_gaps", _wrap(detect_gaps_node, db))
    graph.add_node("store_memory", _wrap(store_profile_memory_node, db))

    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "analyze_github")
    graph.add_edge("analyze_github", "research_role")
    graph.add_edge("research_role", "detect_gaps")
    graph.add_edge("detect_gaps", "store_memory")
    graph.add_edge("store_memory", END)

    return graph.compile()


def build_roadmap_graph(db: AsyncSession):
    graph = StateGraph(AgentState)
    graph.add_node("retrieve_context", _wrap(retrieve_context_node, db))
    graph.add_node("research_role", _wrap(research_role_node, db))
    graph.add_node("generate_roadmap", _wrap(generate_roadmap_node, db))
    graph.add_node("store_roadmap", _wrap(store_roadmap_memory_node, db))

    graph.set_entry_point("retrieve_context")
    graph.add_edge("retrieve_context", "research_role")
    graph.add_edge("research_role", "generate_roadmap")
    graph.add_edge("generate_roadmap", "store_roadmap")
    graph.add_edge("store_roadmap", END)

    return graph.compile()


def build_interview_graph(db: AsyncSession):
    graph = StateGraph(AgentState)

    async def route_after_decide(state: AgentState) -> str:
        if state.get("next_step") == "summarize":
            return "summarize"
        return "generate_question"

    graph.add_node("load_context", _wrap(load_interview_context_node, db))
    graph.add_node("generate_question", _wrap(generate_question_node, db))
    graph.add_node("evaluate_answer", _wrap(evaluate_answer_node, db))
    graph.add_node("decide_next", _wrap(decide_next_node, db))
    graph.add_node("summarize", _wrap(summarize_session_node, db))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "generate_question")
    graph.add_edge("generate_question", END)

    return graph.compile()


async def run_full_onboarding(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_data: dict[str, Any],
    resume_text: str,
    github_username: str,
    github_token: str | None = None,
) -> dict[str, Any]:
    initial_state: AgentState = {
        "user_id": str(user_id),
        "goal_id": str(goal_data.get("id", "")),
        "goal": f"{goal_data['target_company']} {goal_data['target_role']}",
        "target_company": goal_data["target_company"],
        "target_role": goal_data["target_role"],
        "level": goal_data.get("level", "internship"),
        "resume_text": resume_text,
        "github_username": github_username,
    }

    profile_graph = build_profile_graph(db, github_token)
    profile_result = await profile_graph.ainvoke(initial_state)

    merged_state = {**initial_state, **profile_result}
    roadmap_graph = build_roadmap_graph(db)
    roadmap_result = await roadmap_graph.ainvoke(merged_state)

    return {**profile_result, **roadmap_result}
