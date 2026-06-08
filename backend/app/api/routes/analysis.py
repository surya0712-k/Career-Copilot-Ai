import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_full_onboarding, run_profile_phase, run_roadmap_phase
from app.agents.nodes.profile import _collect_memory_chunks
from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.memory.qdrant_client import ensure_collection
from app.memory.store import MemoryStore
from app.memory.types import ROADMAP_UPDATE
from app.models import AnalysisJob, Goal, Profile, User
from app.observability.timing import TimingReport, timed_step
from app.schemas import AnalysisJobResponse, AnalysisRunRequest, ProfileResponse
from app.config import get_settings
from app.services.career.roadmap import RoadmapService
from app.services.progress_service import get_or_create_progress

router = APIRouter()

STEP_LABELS = {
    "profile": "Reviewing GitHub & detecting skill gaps...",
    "gaps_ready": "Gaps ready — building your roadmap...",
    "roadmap": "Building your personalized roadmap...",
    "saving": "Saving results...",
}


async def _update_job_step(job_id: uuid.UUID, step: str, extra: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
        job = result.scalar_one_or_none()
        if job and job.status == "running":
            payload = {**(job.result or {}), "step": step, "step_label": STEP_LABELS.get(step, step)}
            if extra:
                payload.update(extra)
            job.result = payload
            await db.commit()


async def _write_deferred_memory(
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    chunks: list[tuple[str, str, dict | None]],
    roadmap_data: dict,
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            async with timed_step(None, "deferred_memory"):
                store = MemoryStore(db)
                if chunks:
                    await store.store_chunks_parallel(user_id, chunks, goal_id=goal_id)
                if roadmap_data:
                    summaries = [
                        f"Week {m.get('week_start')}-{m.get('week_end')}: {m.get('title')}"
                        for m in roadmap_data.get("milestones", [])
                    ]
                    content = f"Roadmap '{roadmap_data.get('title', '')}': " + "; ".join(summaries)
                    await store.store_chunk(
                        user_id,
                        content,
                        ROADMAP_UPDATE,
                        goal_id=goal_id,
                        metadata={"roadmap": roadmap_data},
                        source_id=str(roadmap_id),
                        upsert=True,
                    )
            await db.commit()
        except Exception:
            await db.rollback()


def _collect_memory_chunks_from_state(result: dict) -> list[tuple[str, str, dict | None]]:
    return _collect_memory_chunks(
        {
            "resume_analysis": result.get("resume_analysis"),
            "github_analysis": result.get("github_analysis"),
            "gap_analysis": result.get("gap_analysis"),
        }
    )


async def _run_analysis_job(job_id: uuid.UUID, user_id: uuid.UUID, goal_id: uuid.UUID):
    report = TimingReport(f"analysis_job:{job_id}")
    async with AsyncSessionLocal() as db:
        try:
            async with timed_step(report, "ensure_collection"):
                await ensure_collection()
            await _update_job_step(job_id, "profile")

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

            settings = get_settings()

            if settings.split_onboarding_phases:
                async with timed_step(report, "run_profile_phase"):
                    profile_result = await run_profile_phase(
                        db,
                        user_id,
                        goal_data,
                        profile.resume_raw_text,
                        user.github_username,
                        user.github_access_token,
                        resume_parsed=profile.resume_parsed,
                    )

                profile.gap_analysis = profile_result.get("gap_analysis")
                profile.github_data = profile_result.get("github_analysis")
                if resume_analysis := profile_result.get("resume_analysis"):
                    profile.skills_extracted = {"analysis": resume_analysis}

                progress = await get_or_create_progress(db, user_id, goal_id)
                if gaps := profile_result.get("gap_analysis"):
                    progress.readiness_score = gaps.get("readiness_score")

                gaps_payload = {
                    "gap_analysis": profile_result.get("gap_analysis"),
                    "readiness_score": profile_result.get("gap_analysis", {}).get("readiness_score"),
                    "phase": "gaps_ready",
                }
                await _update_job_step(job_id, "gaps_ready", gaps_payload)
                await db.commit()

                await _update_job_step(job_id, "roadmap")
                async with timed_step(report, "run_roadmap_phase"):
                    roadmap_result = await run_roadmap_phase(
                        db,
                        user_id,
                        goal_data,
                        profile.resume_raw_text,
                        user.github_username,
                        profile_result,
                        resume_parsed=profile.resume_parsed,
                    )
                result = {**profile_result, **roadmap_result}
            else:
                async with timed_step(report, "run_full_onboarding"):
                    result = await run_full_onboarding(
                        db,
                        user_id,
                        goal_data,
                        profile.resume_raw_text,
                        user.github_username,
                        user.github_access_token,
                        resume_parsed=profile.resume_parsed,
                        on_step=lambda step: _update_job_step(job_id, step),
                    )

                profile.gap_analysis = result.get("gap_analysis")
                profile.github_data = result.get("github_analysis")
                if resume_analysis := result.get("resume_analysis"):
                    profile.skills_extracted = {"analysis": resume_analysis}

            await _update_job_step(job_id, "saving")

            roadmap_data = result.get("roadmap", {})
            service = RoadmapService()
            async with timed_step(report, "persist_roadmap"):
                roadmap = await service.persist_roadmap(
                    db, user_id, goal_id, roadmap_data, write_memory=False
                )

            progress = await get_or_create_progress(db, user_id, goal_id)
            if gaps := result.get("gap_analysis"):
                progress.readiness_score = gaps.get("readiness_score")

            job.status = "completed"
            job.result = {
                "gap_analysis": result.get("gap_analysis"),
                "roadmap_id": str(roadmap.id),
                "readiness_score": result.get("gap_analysis", {}).get("readiness_score"),
            }
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            report.log_summary({"job_id": str(job_id), "status": "completed"})

            # Defer vector memory writes — off critical path after user sees dashboard
            pending = result.get("pending_memory_chunks") or _collect_memory_chunks_from_state(result)
            if pending or roadmap_data:
                asyncio.create_task(
                    _write_deferred_memory(user_id, goal_id, roadmap.id, pending, roadmap_data)
                )
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
    await db.refresh(job)
    # Commit before returning so the client can poll GET /jobs/{id} immediately.
    await db.commit()

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
