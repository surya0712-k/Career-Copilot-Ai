import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, Roadmap, User
from app.schemas import RoadmapResponse, TaskCompleteRequest
from app.services.career.roadmap import RoadmapService
from app.services.progress_service import complete_task
from app.services.roadmap_utils import compute_completion_pct, load_roadmap_with_milestones

router = APIRouter()


def _roadmap_response(roadmap: Roadmap) -> RoadmapResponse:
    return RoadmapResponse(
        id=roadmap.id,
        title=roadmap.title,
        status=roadmap.status,
        milestones=roadmap.milestones,
        goal_id=roadmap.goal_id,
        version=roadmap.version,
        completion_pct=compute_completion_pct(roadmap.milestone_rows),
        created_at=roadmap.created_at,
    )


@router.get("/{roadmap_id}", response_model=RoadmapResponse)
async def get_roadmap(
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roadmap = await load_roadmap_with_milestones(db, roadmap_id, user.id)
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return _roadmap_response(roadmap)


@router.get("", response_model=list[RoadmapResponse])
async def list_roadmaps(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Roadmap).where(Roadmap.user_id == user.id).order_by(Roadmap.created_at.desc())
    )
    roadmaps = []
    for r in result.scalars().all():
        loaded = await load_roadmap_with_milestones(db, r.id, user.id)
        if loaded:
            roadmaps.append(_roadmap_response(loaded))
    return roadmaps


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
        .where(Roadmap.goal_id == goal_id, Roadmap.user_id == user.id, Roadmap.status == "active")
        .order_by(Roadmap.created_at.desc())
        .limit(1)
    )
    roadmap = result.scalar_one_or_none()
    if roadmap is None:
        return None
    loaded = await load_roadmap_with_milestones(db, roadmap.id, user.id)
    return _roadmap_response(loaded) if loaded else None


@router.patch("/{roadmap_id}/tasks/{milestone_id}/{task_index}")
async def complete_roadmap_task(
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    task_index: int,
    body: TaskCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await complete_task(
            db,
            user.id,
            roadmap_id,
            milestone_id,
            task_index,
            body.study_minutes,
            completed=body.completed,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{roadmap_id}/recalculate", response_model=RoadmapResponse)
async def recalculate_roadmap(
    roadmap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RoadmapService()
    try:
        new_roadmap = await service.recalculate(db, user.id, roadmap_id)
        await db.commit()
        loaded = await load_roadmap_with_milestones(db, new_roadmap.id, user.id)
        return _roadmap_response(loaded) if loaded else _roadmap_response(new_roadmap)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


