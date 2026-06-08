import uuid

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.models import Goal, Milestone, Profile, Roadmap, User
from app.services.career.interview import build_milestone_interview_context
from app.services.roadmap_utils import load_roadmap_with_milestones, normalize_task

router = APIRouter()
settings = get_settings()


class LiveKitTokenRequest(BaseModel):
    goal_id: uuid.UUID | None = None
    roadmap_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None


class LiveKitTokenResponse(BaseModel):
    token: str
    url: str
    room_name: str
    identity: str
    focus_label: str | None = None


@router.post("/token", response_model=LiveKitTokenResponse)
async def create_livekit_token(
    body: LiveKitTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.livekit_api_key or not settings.livekit_api_secret or not settings.livekit_url:
        raise HTTPException(status_code=500, detail="LiveKit is not configured")

    metadata = "General software engineering mock interview"
    focus_label: str | None = None
    goal: Goal | None = None

    if body.goal_id:
        result = await db.execute(
            select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id)
        )
        goal = result.scalar_one_or_none()

    if body.milestone_id and body.roadmap_id:
        roadmap = await load_roadmap_with_milestones(db, body.roadmap_id, user.id)
        if roadmap is None:
            raise HTTPException(status_code=404, detail="Roadmap not found")
        milestone = next((m for m in roadmap.milestone_rows if m.id == body.milestone_id), None)
        if milestone is None:
            raise HTTPException(status_code=404, detail="Milestone not found")
        if goal is None:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == roadmap.goal_id, Goal.user_id == user.id)
            )
            goal = goal_result.scalar_one_or_none()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")

        profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        dsa_language = (profile.preferred_dsa_language if profile else None) or "python"

        prior = [
            m.title
            for m in sorted(roadmap.milestone_rows, key=lambda x: x.week_start or 0)
            if m.id != milestone.id and (m.week_start or 0) < (milestone.week_start or 0)
        ]
        tasks = [normalize_task(t) for t in (milestone.tasks or [])]
        metadata = build_milestone_interview_context(
            goal_company=goal.target_company,
            goal_role=goal.target_role,
            goal_level=goal.level,
            milestone_title=milestone.title,
            milestone_description=milestone.description or "",
            week_start=milestone.week_start,
            week_end=milestone.week_end,
            tasks=tasks,
            dsa_language=dsa_language,
            practice_projects=goal.practice_projects,
            prior_milestones=prior,
        )
        focus_label = f"Week {milestone.week_start}-{milestone.week_end}: {milestone.title}"
    elif goal:
        metadata = (
            f"Target: {goal.target_role} at {goal.target_company} ({goal.level}). "
            f"Conduct a tailored mock interview for this role."
        )

    room_name = f"interview-{user.id}-{uuid.uuid4().hex[:8]}"
    identity = f"{user.github_username or user.id}-{uuid.uuid4().hex[:6]}"

    lk = api.LiveKitAPI(
        settings.livekit_url.replace("wss://", "https://").replace("ws://", "http://"),
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )
    try:
        await lk.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=120,
                departure_timeout=20,
                max_participants=2,
            )
        )
        await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="career-interviewer",
                room=room_name,
                metadata=metadata,
            )
        )
    finally:
        await lk.aclose()

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(user.github_username or str(user.id))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return LiveKitTokenResponse(
        token=token,
        url=settings.livekit_url,
        room_name=room_name,
        identity=identity,
        focus_label=focus_label,
    )
