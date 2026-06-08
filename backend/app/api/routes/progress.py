import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.memory.retriever import build_rag_hits
from app.models import Goal, Profile, User
from app.schemas import (
    MemoryAskRequest,
    MemoryAskResponse,
    MemoryNoteCreate,
    ProgressResponse,
    StudySessionCreate,
)
from app.services.career.memory import MemoryService
from app.services.llm import get_llm
from app.services.progress_service import get_progress_summary, log_study_session

router = APIRouter()


@router.get("/me", response_model=ProgressResponse)
async def get_my_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    goal_result = await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.is_active.is_(True)).limit(1)
    )
    goal = goal_result.scalar_one_or_none()
    goal_id = goal.id if goal else None

    from app.memory.retriever import build_rag_context

    memories: list[str] = []
    hits = []
    try:
        memories = await build_rag_context(
            db, user.id, "career progress interview improvement", goal_id=goal_id, limit=15
        )
        hits = await build_rag_hits(db, user.id, "career progress", goal_id=goal_id, limit=5)
    except Exception:
        memories = []
        hits = []

    progress_data = await get_progress_summary(db, user.id, goal_id)

    profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    gap_improvements = []
    if profile and profile.gap_analysis:
        gap_improvements = profile.gap_analysis.get("recommendations", [])[:5]

    summary = _build_progress_summary(progress_data, gap_improvements)
    try:
        llm = get_llm()
        summary_resp = await llm.ainvoke(
            [
                SystemMessage(content="Summarize the user's career coaching progress in 2-3 sentences."),
                HumanMessage(
                    content=(
                        f"Progress data: {progress_data}\n"
                        f"Interview scores: {progress_data.get('recent_interview_scores', [])}\n"
                        f"Memory: {memories[:8]}\nGaps: {gap_improvements}"
                    )
                ),
            ]
        )
        if summary_resp.content:
            summary = summary_resp.content
    except Exception:
        pass

    return ProgressResponse(
        user_id=user.id,
        summary=summary,
        interview_scores=progress_data.get("recent_interview_scores", []),
        gap_improvements=gap_improvements,
        recent_memory=[h.content for h in hits],
        completion_pct=progress_data.get("completion_pct", 0.0),
        total_study_hours=progress_data.get("total_study_hours", 0.0),
        completed_topics=progress_data.get("completed_topics", []),
        weak_areas=progress_data.get("weak_areas", []),
        current_week=progress_data.get("current_week"),
        readiness_score=progress_data.get("readiness_score"),
    )


def _build_progress_summary(progress_data: dict, gap_improvements: list[str]) -> str:
    pct = progress_data.get("completion_pct", 0.0)
    hours = progress_data.get("total_study_hours", 0.0)
    topics = progress_data.get("completed_topics", [])
    readiness = progress_data.get("readiness_score")
    parts = [f"Roadmap {pct:.0f}% complete."]
    if hours:
        parts.append(f"{hours:.1f} study hours logged.")
    if topics:
        parts.append(f"Completed topics: {', '.join(topics[:3])}.")
    if readiness is not None:
        parts.append(f"Readiness score: {readiness}/10.")
    elif gap_improvements:
        parts.append(f"Focus next: {gap_improvements[0]}.")
    return " ".join(parts)


@router.post("/study-session")
async def create_study_session(
    body: StudySessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    goal_result = await db.execute(
        select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id)
    )
    if goal_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    progress = await log_study_session(
        db, user.id, body.goal_id, body.topic, body.duration_minutes, body.notes
    )

    from app.memory.store import MemoryStore
    from app.memory.types import STUDY_LOG

    store = MemoryStore(db)
    await store.store_chunk(
        user.id,
        f"Study session: {body.topic} for {body.duration_minutes} minutes. {body.notes or ''}",
        STUDY_LOG,
        goal_id=body.goal_id,
        metadata={"duration_minutes": body.duration_minutes, "topic": body.topic},
    )
    await db.commit()
    return {"total_study_hours": progress.total_study_hours}
