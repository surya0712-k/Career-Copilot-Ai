import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Goal, User
from app.schemas import MemoryAskRequest, MemoryAskResponse, MemoryNoteCreate
from app.services.career.memory import MemoryService

router = APIRouter()


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=1),
    goal_id: uuid.UUID | None = None,
    chunk_types: str | None = None,
    limit: int = 8,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    types = [t.strip() for t in chunk_types.split(",")] if chunk_types else None
    service = MemoryService()
    hits = await service.retrieve(db, user.id, q, types, goal_id, limit)
    return {"hits": hits}


@router.post("/notes")
async def save_note(
    body: MemoryNoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.goal_id:
        goal_result = await db.execute(
            select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id)
        )
        if goal_result.scalar_one_or_none() is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Goal not found")

    service = MemoryService()
    result = await service.save_note(db, user.id, body.content, body.goal_id)
    await db.commit()
    return result


@router.post("/ask", response_model=MemoryAskResponse)
async def ask_coach(
    body: MemoryAskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MemoryService()
    result = await service.ask(db, user.id, body.question, body.goal_id)
    return MemoryAskResponse(**result)
