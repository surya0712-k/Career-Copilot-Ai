import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, Roadmap, User
from app.schemas import RoadmapResponse

router = APIRouter()


@router.get("/{roadmap_id}", response_model=RoadmapResponse)
async def get_roadmap(
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Roadmap).where(Roadmap.id == roadmap_id, Roadmap.user_id == user.id)
    )
    roadmap = result.scalar_one_or_none()
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return RoadmapResponse.model_validate(roadmap)


@router.get("", response_model=list[RoadmapResponse])
async def list_roadmaps(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Roadmap).where(Roadmap.user_id == user.id).order_by(Roadmap.created_at.desc())
    )
    return [RoadmapResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/goal/{goal_id}/latest", response_model=RoadmapResponse | None)
async def get_latest_roadmap_for_goal(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    goal_result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id)
    )
    if goal_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    result = await db.execute(
        select(Roadmap)
        .where(Roadmap.goal_id == goal_id, Roadmap.user_id == user.id)
        .order_by(Roadmap.created_at.desc())
        .limit(1)
    )
    roadmap = result.scalar_one_or_none()
    if roadmap is None:
        return None
    return RoadmapResponse.model_validate(roadmap)
