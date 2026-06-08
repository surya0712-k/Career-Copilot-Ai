import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.services.progress_service import get_progress_summary


async def load_progress_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    goal_id = uuid.UUID(state["goal_id"]) if state.get("goal_id") else None
    progress = await get_progress_summary(db, user_id, goal_id)
    return {"progress_data": progress}


async def merge_completed_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    roadmap = state.get("roadmap", {})
    completed = state.get("progress_data", {}).get("completed_topics", [])
    for m in roadmap.get("milestones", []):
        for t in m.get("tasks", []):
            if t.get("title") in completed:
                t["completed"] = True
    return {"roadmap": roadmap}
