from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.memory.store import MemoryStore
from app.memory.types import DSA_PREFERENCE
from app.models import Goal, Profile, User
from app.observability.timing import timed_step
from app.schemas import ProfilePreferencesUpdate, ProfileResponse
from app.services.prompt_context import DSA_LANGUAGE_LABELS
from app.services.resume_parser import extract_resume_fast

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse.model_validate(profile)


@router.post("/resume", response_model=ProfileResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    async with timed_step(None, "upload_resume"):
        try:
            raw_text, parsed = extract_resume_fast(content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        result = await db.execute(select(Profile).where(Profile.user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = Profile(user_id=user.id)
            db.add(profile)

        profile.resume_raw_text = raw_text
        profile.resume_parsed = parsed
        profile.skills_extracted = {"skills": parsed.get("skills", [])}
        await db.flush()

    return ProfileResponse.model_validate(profile)


@router.patch("/me/preferences", response_model=ProfileResponse)
async def update_profile_preferences(
    body: ProfilePreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile(user_id=user.id, preferred_dsa_language=body.preferred_dsa_language)
        db.add(profile)
    else:
        profile.preferred_dsa_language = body.preferred_dsa_language
    await db.flush()

    goal_result = await db.execute(
        select(Goal).where(Goal.user_id == user.id, Goal.is_active.is_(True)).limit(1)
    )
    goal = goal_result.scalar_one_or_none()
    label = DSA_LANGUAGE_LABELS.get(body.preferred_dsa_language, body.preferred_dsa_language)
    store = MemoryStore(db)
    await store.store_chunk(
        user.id,
        f"Preferred DSA coding language: {label}. Use for roadmap coding tasks and mock interviews.",
        DSA_PREFERENCE,
        goal_id=goal.id if goal else None,
        source_id=f"dsa_pref_{user.id}",
        upsert=True,
    )

    return ProfileResponse.model_validate(profile)
