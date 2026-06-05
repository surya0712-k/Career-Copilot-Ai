import uuid

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.memory.retriever import build_rag_context
from app.models import InterviewSession, Profile, User
from app.schemas import ProgressResponse
from app.services.llm import get_llm

router = APIRouter()


@router.get("/me", response_model=ProgressResponse)
async def get_my_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memories = await build_rag_context(
        db, user.id, "career progress interview improvement", limit=15
    )

    interview_result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id, InterviewSession.score.isnot(None))
        .order_by(InterviewSession.created_at.desc())
        .limit(10)
    )
    interviews = interview_result.scalars().all()
    interview_scores = [
        {
            "session_id": str(i.id),
            "score": i.score,
            "role_context": i.role_context,
            "date": i.created_at.isoformat() if i.created_at else None,
        }
        for i in interviews
    ]

    profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    gap_improvements = []
    if profile and profile.gap_analysis:
        gap_improvements = profile.gap_analysis.get("recommendations", [])[:5]

    llm = get_llm()
    summary_resp = await llm.ainvoke(
        [
            SystemMessage(content="Summarize the user's career coaching progress in 2-3 sentences."),
            HumanMessage(
                content=f"Interview scores: {interview_scores}\nMemory: {memories[:8]}\nGaps: {gap_improvements}"
            ),
        ]
    )

    return ProgressResponse(
        user_id=user.id,
        summary=summary_resp.content,
        interview_scores=interview_scores,
        gap_improvements=gap_improvements,
        recent_memory=memories[:5],
    )
