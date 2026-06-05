import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import EVALUATE_ANSWER_PROMPT, INTERVIEWER_PROMPT, SESSION_SUMMARY_PROMPT
from app.agents.state import AgentState
from app.memory.retriever import build_rag_context, format_rag_context
from app.memory.store import MemoryStore
from app.services.llm import get_llm


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


async def load_interview_context_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    user_id = uuid.UUID(state["user_id"])
    query = state.get("role_context") or state.get("goal", "mock interview")
    memories = await build_rag_context(
        db,
        user_id,
        query,
        chunk_types=["resume_insight", "github_insight", "gap_finding", "roadmap_update", "interview_feedback"],
        limit=12,
    )
    context_str = await format_rag_context(memories)
    return {
        "retrieved_memory": memories,
        "interview_context": {"rag_context": context_str},
        "turn_number": state.get("turn_number", 0),
        "max_turns": state.get("max_turns", 5),
    }


async def generate_question_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    turn = state.get("turn_number", 0) + 1
    context = state.get("interview_context", {}).get("rag_context", "")

    prompt = INTERVIEWER_PROMPT.format(
        company=state.get("target_company", "the company"),
        role=state.get("target_role", "software engineer"),
        level=state.get("level", "internship"),
        context=context,
    )

    messages = [SystemMessage(content=prompt)]
    for msg in state.get("messages", [])[-6:]:
        messages.append(msg)

    if turn == 1:
        messages.append(
            HumanMessage(content="Start the interview with a brief introduction and your first question.")
        )
    else:
        messages.append(HumanMessage(content="Ask your next question based on the conversation so far."))

    response = await llm.ainvoke(messages)
    return {
        "current_question": response.content,
        "turn_number": turn,
        "messages": [response],
    }


async def evaluate_answer_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    structured_llm = llm.with_structured_output(AnswerEvaluation)

    result: AnswerEvaluation = await structured_llm.ainvoke(
        [
            SystemMessage(content=EVALUATE_ANSWER_PROMPT),
            HumanMessage(
                content=(
                    f"Question: {state.get('current_question', '')}\n\n"
                    f"Answer: {state.get('current_answer', '')}\n\n"
                    f"Target role: {state.get('target_company')} {state.get('target_role')}"
                )
            ),
        ]
    )

    user_id = uuid.UUID(state["user_id"])
    store = MemoryStore(db)
    feedback_text = (
        f"Interview Q: {state.get('current_question', '')[:200]}. "
        f"Score: {result.score}. Feedback: {result.feedback}"
    )
    await store.store_chunk(
        user_id,
        feedback_text,
        "interview_feedback",
        metadata={"score": result.score, "turn": state.get("turn_number")},
    )

    return {
        "interview_context": {
            **state.get("interview_context", {}),
            "last_evaluation": result.model_dump(),
        },
    }


async def decide_next_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    turn = state.get("turn_number", 0)
    max_turns = state.get("max_turns", 5)
    if turn >= max_turns:
        return {"next_step": "summarize"}
    return {"next_step": "continue"}


async def summarize_session_node(state: AgentState, db: AsyncSession) -> dict[str, Any]:
    llm = get_llm()
    structured_llm = llm.with_structured_output(SessionSummary)

    conversation = []
    for msg in state.get("messages", []):
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))
        conversation.append(f"{role}: {content}")

    result: SessionSummary = await structured_llm.ainvoke(
        [
            SystemMessage(content=SESSION_SUMMARY_PROMPT),
            HumanMessage(content="\n".join(conversation)[:12000]),
        ]
    )

    user_id = uuid.UUID(state["user_id"])
    store = MemoryStore(db)
    await store.store_chunk(
        user_id,
        f"Interview session summary: score {result.overall_score}. {result.readiness}",
        "interview_feedback",
        metadata=result.model_dump(),
    )

    return {
        "interview_context": {
            **state.get("interview_context", {}),
            "summary": result.model_dump(),
        },
        "next_step": "done",
    }
