import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_full_onboarding
from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.memory.qdrant_client import ensure_collection
from app.models import AnalysisJob, Goal, Milestone, Profile, Roadmap, User
from app.schemas import AnalysisJobResponse, AnalysisRunRequest, ProfileResponse

router = APIRouter()


async def _run_analysis_job(job_id: uuid.UUID, user_id: uuid.UUID, goal_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        try:
            await ensure_collection()

            job_result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
            job = job_result.scalar_one()

            goal_result = await db.execute(select(Goal).where(Goal.id == goal_id))
            goal = goal_result.scalar_one()

            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one()

            profile_result = await db.execute(select(Profile).where(Profile.user_id == user_id))
            profile = profile_result.scalar_one_or_none()

            if not profile or not profile.resume_raw_text:
                job.status = "failed"
                job.error = "Resume not uploaded"
                await db.commit()
                return

            goal_data = {
                "id": str(goal.id),
                "target_company": goal.target_company,
                "target_role": goal.target_role,
                "level": goal.level,
            }

            result = await run_full_onboarding(
                db,
                user_id,
                goal_data,
                profile.resume_raw_text,
                user.github_username,
                user.github_access_token,
            )

            profile.gap_analysis = result.get("gap_analysis")
            profile.github_data = result.get("github_analysis")
            if resume_analysis := result.get("resume_analysis"):
                profile.skills_extracted = {"analysis": resume_analysis}

            roadmap_data = result.get("roadmap", {})
            roadmap = Roadmap(
                user_id=user_id,
                goal_id=goal_id,
                title=roadmap_data.get("title", f"Roadmap for {goal.target_company}"),
                milestones=roadmap_data.get("milestones", []),
                status="active",
            )
            db.add(roadmap)
            await db.flush()

            for m in roadmap_data.get("milestones", []):
                milestone = Milestone(
                    roadmap_id=roadmap.id,
                    title=m.get("title", ""),
                    description=m.get("description"),
                    week_start=m.get("week_start"),
                    week_end=m.get("week_end"),
                    tasks=[t if isinstance(t, dict) else {"title": str(t)} for t in m.get("tasks", [])],
                )
                db.add(milestone)

            job.status = "completed"
            job.result = {
                "gap_analysis": result.get("gap_analysis"),
                "roadmap_id": str(roadmap.id),
                "readiness_score": result.get("gap_analysis", {}).get("readiness_score"),
            }
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            await db.rollback()
            async with AsyncSessionLocal() as err_db:
                job_result = await err_db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    await err_db.commit()


@router.post("/run", response_model=AnalysisJobResponse)
async def run_analysis(
    body: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_collection()

    goal_result = await db.execute(
        select(Goal).where(Goal.id == body.goal_id, Goal.user_id == user.id)
    )
    goal = goal_result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    profile_result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile or not profile.resume_raw_text:
        raise HTTPException(status_code=400, detail="Upload a resume before running analysis")

    job = AnalysisJob(user_id=user.id, goal_id=goal.id, status="running")
    db.add(job)
    await db.flush()

    background_tasks.add_task(_run_analysis_job, job.id, user.id, goal.id)

    return AnalysisJobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return AnalysisJobResponse.model_validate(job)


@router.get("/me", response_model=ProfileResponse | None)
async def get_my_analysis(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    return ProfileResponse.model_validate(profile)
