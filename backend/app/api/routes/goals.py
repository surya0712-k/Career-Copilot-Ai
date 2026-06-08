import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, User
from app.schemas import GoalCreate, GoalResponse, PracticeProjectsUpdate

router = APIRouter()


@router.post("", response_model=GoalResponse)
async def create_goal(
    body: GoalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(update(Goal).where(Goal.user_id == user.id).values(is_active=False))

    goal = Goal(
        user_id=user.id,
        target_company=body.target_company,
        target_role=body.target_role,
        level=body.level,
        description=body.description,
        is_active=True,
    )
    db.add(goal)
    await db.flush()

    from app.memory.store import MemoryStore
    from app.memory.types import GOAL_INTENT

    store = MemoryStore(db)
    await store.store_chunk(
        user.id,
        f"Career goal: {body.target_role} at {body.target_company} ({body.level}). {body.description or ''}",
        GOAL_INTENT,
        goal_id=goal.id,
        source_id=str(goal.id),
        upsert=True,
    )

    return GoalResponse.model_validate(goal)


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Goal).where(Goal.user_id == user.id).order_by(Goal.created_at.desc()))
    return [GoalResponse.model_validate(g) for g in result.scalars().all()]


@router.get("/active", response_model=GoalResponse | None)
async def get_active_goal(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.is_active.is_(True)).limit(1)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        return None
    return GoalResponse.model_validate(goal)


@router.get("/{goal_id}/practice-projects", response_model=list[dict])
async def get_practice_projects(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    goal = await _get_user_goal(db, goal_id, user.id)
    return goal.practice_projects or []


@router.put("/{goal_id}/practice-projects", response_model=list[dict])
async def update_practice_projects(
    goal_id: uuid.UUID,
    body: PracticeProjectsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(body.projects) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 practice projects allowed")
    goal = await _get_user_goal(db, goal_id, user.id)
    goal.practice_projects = [p.model_dump() for p in body.projects]
    await db.flush()
    return goal.practice_projects


async def _get_user_goal(db: AsyncSession, goal_id: uuid.UUID, user_id: uuid.UUID) -> Goal:
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal
