from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    user_id: str
    goal_id: str
    goal: str
    target_company: str
    target_role: str
    level: str
    resume_text: str
    resume_analysis: dict[str, Any]
    github_username: str
    github_analysis: dict[str, Any]
    role_research: dict[str, Any]
    gap_analysis: dict[str, Any]
    roadmap: dict[str, Any]
    interview_session_id: str
    interview_context: dict[str, Any]
    current_question: str
    current_answer: str
    turn_number: int
    max_turns: int
    retrieved_memory: list[str]
    messages: Annotated[list, add_messages]
    next_step: str
    error: str


WorkflowType = Literal["profile", "roadmap", "interview", "progress"]
