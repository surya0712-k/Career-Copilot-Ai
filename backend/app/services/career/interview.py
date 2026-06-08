import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    EVALUATE_ANSWER_PROMPT,
    INTERVIEWER_PROMPT,
    SESSION_SUMMARY_PROMPT,
)
from app.memory.retriever import build_rag_context, format_rag_context
from app.memory.store import MemoryStore
from app.memory.types import INTERVIEW_FEEDBACK, INTERVIEW_STRENGTH, INTERVIEW_WEAKNESS
from app.services.llm import get_llm
from app.services.progress_service import get_or_create_progress, upsert_weak_areas


class AnswerEvaluation(BaseModel):
    score: float = Field(ge=1, le=10)
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    follow_up: str | None = None


class SessionSummary(BaseModel):
    overall_score: float = Field(ge=1, le=10)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    readiness: str = ""


def build_milestone_interview_context(
    *,
    goal_company: str,
    goal_role: str,
    goal_level: str,
    milestone_title: str,
    milestone_description: str,
    week_start: int | None,
    week_end: int | None,
    tasks: list[dict],
    dsa_language: str,
    practice_projects: list[dict] | None,
    prior_milestones: list[str] | None = None,
) -> str:
    from app.services.prompt_context import DSA_LANGUAGE_LABELS

    week = f"Week {week_start}-{week_end}" if week_start else "This week"
    task_lines = [
        f"- {t.get('title', '')}: {t.get('description', '')}"
        for t in tasks
        if t.get("title")
    ]
    project_lines = []
    for p in practice_projects or []:
        name = p.get("name", "")
        desc = p.get("description", "")
        if name:
            project_lines.append(f"- {name}: {desc}")

    parts = [
        f"Conduct a mock interview focused on {week} — {milestone_title}.",
        f"Target role: {goal_role} at {goal_company} ({goal_level}).",
        f"Milestone goals: {milestone_description}",
        "Tasks to assess:",
        *task_lines,
        f"DSA / coding language preference: {DSA_LANGUAGE_LABELS.get(dsa_language, dsa_language)}.",
    ]
    if prior_milestones:
        parts.append(f"Prior weeks already covered: {', '.join(prior_milestones)}.")
    if project_lines:
        parts.append("Practice projects (ASK about these — candidate built them for prep):")
        parts.extend(project_lines)
    else:
        parts.append("No custom practice projects on file.")
    parts.append(
        "Do NOT ask about resume or GitHub projects unless the candidate brings them up."
    )
    return "\n".join(parts)[:2000]


class InterviewService:
    async def load_context(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        role_context: str,
        goal_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        memories = await build_rag_context(
            db,
            user_id,
            role_context,
            chunk_types=None,
            goal_id=goal_id,
            limit=12,
        )
        context_str = await format_rag_context(memories)
        return {"retrieved_memory": memories, "rag_context": context_str}

    async def generate_question(
        self,
        db: AsyncSession,
        target_company: str,
        target_role: str,
        level: str,
        rag_context: str,
        turn_number: int,
        messages: list | None = None,
    ) -> str:
        llm = get_llm()
        prompt = INTERVIEWER_PROMPT.format(
            company=target_company,
            role=target_role,
            level=level,
            context=rag_context,
        )
        msg_list = [SystemMessage(content=prompt)]
        for msg in (messages or [])[-6:]:
            msg_list.append(msg)
        if turn_number == 1:
            msg_list.append(
                HumanMessage(content="Start the interview with a brief introduction and your first question.")
            )
        else:
            msg_list.append(HumanMessage(content="Ask your next question based on the conversation so far."))
        response = await llm.ainvoke(msg_list)
        return response.content

    async def evaluate_answer(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        goal_id: uuid.UUID | None,
        question: str,
        answer: str,
        target_company: str,
        target_role: str,
        turn_number: int,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        llm = get_llm()
        structured_llm = llm.with_structured_output(AnswerEvaluation)
        result: AnswerEvaluation = await structured_llm.ainvoke(
            [
                SystemMessage(content=EVALUATE_ANSWER_PROMPT),
                HumanMessage(
                    content=(
                        f"Question: {question}\n\nAnswer: {answer}\n\n"
                        f"Target role: {target_company} {target_role}"
                    )
                ),
            ]
        )
        store = MemoryStore(db)
        feedback_text = (
            f"Interview Q: {question[:300]}. Score: {result.score}. "
            f"Feedback: {result.feedback}. Improvements: {result.improvements}. "
            f"Strengths: {result.strengths}"
        )
        await store.store_chunk(
            user_id,
            feedback_text,
            INTERVIEW_FEEDBACK,
            goal_id=goal_id,
            metadata=result.model_dump(),
            session_id=session_id,
            score=result.score,
        )
        for imp in result.improvements:
            await store.store_chunk(
                user_id,
                f"Interview weakness: {imp}",
                INTERVIEW_WEAKNESS,
                goal_id=goal_id,
                metadata={"turn": turn_number, "score": result.score},
                session_id=session_id,
            )
        for s in result.strengths:
            await store.store_chunk(
                user_id,
                f"Interview strength: {s}",
                INTERVIEW_STRENGTH,
                goal_id=goal_id,
                metadata={"turn": turn_number},
                session_id=session_id,
            )
        return result.model_dump()

    async def summarize_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        goal_id: uuid.UUID | None,
        conversation: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        llm = get_llm()
        structured_llm = llm.with_structured_output(SessionSummary)
        result: SessionSummary = await structured_llm.ainvoke(
            [
                SystemMessage(content=SESSION_SUMMARY_PROMPT),
                HumanMessage(content=conversation[:12000]),
            ]
        )
        store = MemoryStore(db)
        await store.store_chunk(
            user_id,
            f"Interview session summary: score {result.overall_score}. {result.readiness}. "
            f"Improvements: {result.improvements}. Strengths: {result.strengths}",
            INTERVIEW_FEEDBACK,
            goal_id=goal_id,
            metadata=result.model_dump(),
            source_id=session_id,
            session_id=session_id,
            score=result.overall_score,
            upsert=bool(session_id),
        )
        if goal_id and result.improvements:
            await upsert_weak_areas(db, user_id, goal_id, result.improvements, source="interview")
            progress = await get_or_create_progress(db, user_id, goal_id)
            progress.last_interview_score = result.overall_score
        return result.model_dump()
