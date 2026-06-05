from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, User
from app.schemas import GoalCreate, GoalResponse

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
