import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class GitHubAuthRequest(BaseModel):
    code: str


class UserResponse(BaseModel):
    id: uuid.UUID
    github_id: str
    github_username: str
    email: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class GoalCreate(BaseModel):
    target_company: str
    target_role: str
    level: str = "internship"
    description: str | None = None


class GoalResponse(BaseModel):
    id: uuid.UUID
    target_company: str
    target_role: str
    level: str
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    id: uuid.UUID
    resume_parsed: dict | None = None
    github_data: dict | None = None
    skills_extracted: dict | None = None
    gap_analysis: dict | None = None

    model_config = {"from_attributes": True}


class AnalysisRunRequest(BaseModel):
    goal_id: uuid.UUID


class AnalysisJobResponse(BaseModel):
    id: uuid.UUID
    status: str
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RoadmapResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    milestones: list | None = None
    goal_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewCreate(BaseModel):
    goal_id: uuid.UUID | None = None
    role_context: str | None = None


class InterviewTurnRequest(BaseModel):
    answer: str


class InterviewTurnResponse(BaseModel):
    id: uuid.UUID
    turn_number: int
    question: str
    answer: str | None = None
    feedback: dict | None = None
    score: float | None = None

    model_config = {"from_attributes": True}


class InterviewSessionResponse(BaseModel):
    id: uuid.UUID
    role_context: str
    status: str
    feedback_summary: dict | None = None
    score: float | None = None
    turns: list[InterviewTurnResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ProgressResponse(BaseModel):
    user_id: uuid.UUID
    summary: str
    interview_scores: list[dict]
    gap_improvements: list[str]
    recent_memory: list[str]
