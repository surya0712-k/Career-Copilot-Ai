import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, InterviewSession, InterviewTurn, Roadmap, User
from app.schemas import (
    InterviewCreate,
    InterviewSessionResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
    VoiceInterviewSummary,
)
from app.services.career.interview import InterviewService
from app.services.career.roadmap import RoadmapService

router = APIRouter()
interview_service = InterviewService()


@router.post("", response_model=InterviewSessionResponse)
async def start_interview(
    body: InterviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_company = "Tech Company"
    target_role = "Software Engineer"
    level = "internship"
    goal_id = body.goal_id

    if body.goal_id:
        goal_result = await db.execute(
            select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id)
        )
        goal = goal_result.scalar_one_or_none()
        if goal:
            target_company = goal.target_company
            target_role = goal.target_role
            level = goal.level

    role_context = body.role_context or f"{target_company} {target_role} {level}"

    session = InterviewSession(
        user_id=user.id,
        goal_id=body.goal_id,
        role_context=role_context,
        status="active",
    )
    db.add(session)
    await db.flush()

    ctx = await interview_service.load_context(db, user.id, role_context, goal_id)
    question = await interview_service.generate_question(
        db, target_company, target_role, level, ctx["rag_context"], 1
    )

    turn = InterviewTurn(
        session_id=session.id,
        turn_number=1,
        question=question,
    )
    db.add(turn)
    await db.flush()

    return InterviewSessionResponse(
        id=session.id,
        role_context=session.role_context,
        status=session.status,
        turns=[InterviewTurnResponse.model_validate(turn)],
    )


async def _maybe_recalculate_roadmap(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID | None) -> None:
    if not goal_id:
        return
    result = await db.execute(
        select(Roadmap)
        .where(Roadmap.goal_id == goal_id, Roadmap.user_id == user_id, Roadmap.status == "active")
        .order_by(Roadmap.created_at.desc())
        .limit(1)
    )
    roadmap = result.scalar_one_or_none()
    if roadmap:
        service = RoadmapService()
        await service.recalculate(db, user_id, roadmap.id)


@router.post("/{session_id}/turn")
async def submit_answer(
    session_id: uuid.UUID,
    body: InterviewTurnRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.id == session_id, InterviewSession.user_id == user.id)
        .options(selectinload(InterviewSession.turns))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Interview session is not active")

    current_turn = max(session.turns, key=lambda t: t.turn_number)
    current_turn.answer = body.answer

    target_company, target_role, level = "Tech Company", "Software Engineer", "internship"
    if session.goal_id:
        goal_result = await db.execute(select(Goal).where(Goal.id == session.goal_id))
        goal = goal_result.scalar_one_or_none()
        if goal:
            target_company, target_role, level = goal.target_company, goal.target_role, goal.level

    feedback = await interview_service.evaluate_answer(
        db,
        user.id,
        session.goal_id,
        current_turn.question,
        body.answer,
        target_company,
        target_role,
        current_turn.turn_number,
        session_id=str(session.id),
    )
    current_turn.feedback = feedback
    current_turn.score = feedback.get("score")

    turn_count = current_turn.turn_number
    max_turns = 5

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {"event": "feedback", "data": json.dumps(feedback)}

        if turn_count >= max_turns:
            conversation = "\n".join(
                f"Q: {t.question}\nA: {t.answer or ''}" for t in sorted(session.turns, key=lambda x: x.turn_number)
            )
            summary = await interview_service.summarize_session(
                db, user.id, session.goal_id, conversation, session_id=str(session.id)
            )
            session.status = "completed"
            session.feedback_summary = summary
            session.score = summary.get("overall_score")
            await db.flush()
            try:
                await _maybe_recalculate_roadmap(db, user.id, session.goal_id)
            except Exception:
                pass
            await db.commit()
            yield {"event": "summary", "data": json.dumps(summary)}
            yield {"event": "done", "data": json.dumps({"status": "completed"})}
        else:
            ctx = await interview_service.load_context(db, user.id, session.role_context, session.goal_id)
            question = await interview_service.generate_question(
                db,
                target_company,
                target_role,
                level,
                ctx["rag_context"],
                turn_count + 1,
            )
            new_turn = InterviewTurn(
                session_id=session.id,
                turn_number=turn_count + 1,
                question=question,
            )
            db.add(new_turn)
            await db.commit()
            yield {
                "event": "question",
                "data": json.dumps({"question": new_turn.question, "turn_number": new_turn.turn_number}),
            }
            yield {"event": "done", "data": json.dumps({"status": "continue"})}

    return EventSourceResponse(event_generator())


@router.post("/voice/summary")
async def save_voice_interview_summary(
    body: VoiceInterviewSummary,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = InterviewSession(
        user_id=user.id,
        goal_id=body.goal_id,
        role_context="Voice mock interview (LiveKit)",
        status="completed",
        feedback_summary={"summary": body.summary, "improvements": body.improvements, "strengths": body.strengths},
        score=body.score,
    )
    db.add(session)
    await db.flush()

    service = InterviewService()
    await service.summarize_session(
        db,
        user.id,
        body.goal_id,
        f"{body.summary}\nImprovements: {body.improvements}\nStrengths: {body.strengths}",
        session_id=str(session.id),
    )
    try:
        await _maybe_recalculate_roadmap(db, user.id, body.goal_id)
    except Exception:
        pass
    await db.commit()
    return {"session_id": str(session.id)}


@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.id == session_id, InterviewSession.user_id == user.id)
        .options(selectinload(InterviewSession.turns))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    turns = sorted(session.turns, key=lambda t: t.turn_number)
    return InterviewSessionResponse(
        id=session.id,
        role_context=session.role_context,
        status=session.status,
        feedback_summary=session.feedback_summary,
        score=session.score,
        turns=[InterviewTurnResponse.model_validate(t) for t in turns],
    )


@router.get("", response_model=list[InterviewSessionResponse])
async def list_interviews(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .options(selectinload(InterviewSession.turns))
        .order_by(InterviewSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [
        InterviewSessionResponse(
            id=s.id,
            role_context=s.role_context,
            status=s.status,
            feedback_summary=s.feedback_summary,
            score=s.score,
            turns=[InterviewTurnResponse.model_validate(t) for t in sorted(s.turns, key=lambda t: t.turn_number)],
        )
        for s in sessions
    ]
