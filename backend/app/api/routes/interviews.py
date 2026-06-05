import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import build_interview_graph
from app.agents.nodes.interview import (
    decide_next_node,
    evaluate_answer_node,
    generate_question_node,
    load_interview_context_node,
    summarize_session_node,
)
from app.agents.state import AgentState
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, InterviewSession, InterviewTurn, User
from app.schemas import InterviewCreate, InterviewSessionResponse, InterviewTurnRequest, InterviewTurnResponse

router = APIRouter()


@router.post("", response_model=InterviewSessionResponse)
async def start_interview(
    body: InterviewCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_company = "Tech Company"
    target_role = "Software Engineer"
    level = "internship"

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

    initial_state: AgentState = {
        "user_id": str(user.id),
        "goal_id": str(body.goal_id) if body.goal_id else "",
        "target_company": target_company,
        "target_role": target_role,
        "level": level,
        "role_context": role_context,
        "interview_session_id": str(session.id),
        "turn_number": 0,
        "max_turns": 5,
        "messages": [],
    }

    ctx_result = await load_interview_context_node(initial_state, db)
    state = {**initial_state, **ctx_result}
    q_result = await generate_question_node(state, db)
    state = {**state, **q_result}

    turn = InterviewTurn(
        session_id=session.id,
        turn_number=1,
        question=state["current_question"],
    )
    db.add(turn)
    await db.flush()

    return InterviewSessionResponse(
        id=session.id,
        role_context=session.role_context,
        status=session.status,
        turns=[InterviewTurnResponse.model_validate(turn)],
    )


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

    state: AgentState = {
        "user_id": str(user.id),
        "target_company": target_company,
        "target_role": target_role,
        "level": level,
        "role_context": session.role_context,
        "interview_session_id": str(session.id),
        "current_question": current_turn.question,
        "current_answer": body.answer,
        "turn_number": current_turn.turn_number,
        "max_turns": 5,
        "messages": [],
    }

    eval_result = await evaluate_answer_node(state, db)
    state = {**state, **eval_result}
    current_turn.feedback = state.get("interview_context", {}).get("last_evaluation")
    current_turn.score = current_turn.feedback.get("score") if current_turn.feedback else None

    decide_result = await decide_next_node(state, db)
    state = {**state, **decide_result}

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {"event": "feedback", "data": json.dumps(current_turn.feedback or {})}

        if state.get("next_step") == "summarize":
            summary_result = await summarize_session_node(state, db)
            summary = summary_result.get("interview_context", {}).get("summary", {})
            session.status = "completed"
            session.feedback_summary = summary
            session.score = summary.get("overall_score")
            await db.flush()
            yield {"event": "summary", "data": json.dumps(summary)}
            yield {"event": "done", "data": json.dumps({"status": "completed"})}
        else:
            q_state = {**state, "turn_number": current_turn.turn_number}
            q_result = await generate_question_node(q_state, db)
            new_turn = InterviewTurn(
                session_id=session.id,
                turn_number=current_turn.turn_number + 1,
                question=q_result["current_question"],
            )
            db.add(new_turn)
            await db.flush()
            yield {
                "event": "question",
                "data": json.dumps({"question": new_turn.question, "turn_number": new_turn.turn_number}),
            }
            yield {"event": "done", "data": json.dumps({"status": "continue"})}

    return EventSourceResponse(event_generator())


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
