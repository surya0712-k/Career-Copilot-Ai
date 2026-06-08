import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompletedTask, Goal, InterviewSession, Milestone, Profile, Roadmap, UserProgress, WeakArea
from app.services.roadmap_utils import compute_completion_pct, load_roadmap_with_milestones, normalize_task


async def get_or_create_progress(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> UserProgress:
    result = await db.execute(
        select(UserProgress).where(UserProgress.user_id == user_id, UserProgress.goal_id == goal_id)
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        profile_result = await db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        readiness = None
        if profile and profile.gap_analysis:
            readiness = profile.gap_analysis.get("readiness_score")
        progress = UserProgress(
            user_id=user_id,
            goal_id=goal_id,
            completed_topics=[],
            weak_areas=[],
            readiness_score=readiness,
        )
        db.add(progress)
        await db.flush()
    return progress


async def complete_task(
    db: AsyncSession,
    user_id: uuid.UUID,
    roadmap_id: uuid.UUID,
    milestone_id: uuid.UUID,
    task_index: int,
    study_minutes: int = 0,
    completed: bool = True,
) -> dict:
    roadmap = await load_roadmap_with_milestones(db, roadmap_id, user_id)
    if roadmap is None:
        raise ValueError("Roadmap not found")

    milestone = next((m for m in roadmap.milestone_rows if m.id == milestone_id), None)
    if milestone is None:
        raise ValueError("Milestone not found")

    tasks = [normalize_task(t) for t in (milestone.tasks or [])]
    if task_index < 0 or task_index >= len(tasks):
        raise ValueError("Invalid task index")

    task = tasks[task_index]
    progress = await get_or_create_progress(db, user_id, roadmap.goal_id)

    if completed:
        if task.get("completed"):
            return {
                "already_completed": True,
                "completion_pct": compute_completion_pct(roadmap.milestone_rows),
                "task": task,
            }
        now = datetime.now(timezone.utc).isoformat()
        task["completed"] = True
        task["completed_at"] = now
        tasks[task_index] = task
        milestone.tasks = tasks

        completed_count = sum(1 for t in tasks if t.get("completed"))
        if completed_count == len(tasks):
            milestone.status = "completed"
        elif completed_count > 0:
            milestone.status = "in_progress"

        db.add(
            CompletedTask(
                user_id=user_id,
                roadmap_id=roadmap_id,
                milestone_id=milestone_id,
                task_title=task["title"],
                topic=task.get("title"),
                study_minutes=study_minutes,
            )
        )

        topics = list(progress.completed_topics or [])
        if task["title"] not in topics:
            topics.append(task["title"])
        progress.completed_topics = topics
        if study_minutes:
            progress.total_study_hours = (progress.total_study_hours or 0) + study_minutes / 60.0
        progress.current_week = milestone.week_start
    else:
        if not task.get("completed"):
            return {
                "already_incomplete": True,
                "completion_pct": compute_completion_pct(roadmap.milestone_rows),
                "task": task,
            }
        task["completed"] = False
        task["completed_at"] = None
        tasks[task_index] = task
        milestone.tasks = tasks

        completed_count = sum(1 for t in tasks if t.get("completed"))
        if completed_count == 0:
            milestone.status = "pending"
        else:
            milestone.status = "in_progress"

        existing = await db.execute(
            select(CompletedTask).where(
                CompletedTask.user_id == user_id,
                CompletedTask.roadmap_id == roadmap_id,
                CompletedTask.milestone_id == milestone_id,
                CompletedTask.task_title == task["title"],
            )
        )
        for row in existing.scalars().all():
            await db.delete(row)

        topics = [t for t in (progress.completed_topics or []) if t != task["title"]]
        progress.completed_topics = topics

    from app.services.roadmap_utils import sync_roadmap_jsonb

    sync_roadmap_jsonb(roadmap)
    await db.flush()

    return {
        "completion_pct": compute_completion_pct(roadmap.milestone_rows),
        "milestone_status": milestone.status,
        "task": task,
    }


async def log_study_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    topic: str,
    duration_minutes: int,
    notes: str | None = None,
) -> UserProgress:
    from app.models import StudySession

    session = StudySession(
        user_id=user_id,
        goal_id=goal_id,
        topic=topic,
        duration_minutes=duration_minutes,
        notes=notes,
    )
    db.add(session)

    progress = await get_or_create_progress(db, user_id, goal_id)
    progress.total_study_hours = (progress.total_study_hours or 0) + duration_minutes / 60.0
    await db.flush()
    return progress


async def upsert_weak_areas(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    topics: list[str],
    source: str = "interview",
) -> list[WeakArea]:
    results = []
    for topic in topics:
        topic = topic.strip()
        if not topic:
            continue
        result = await db.execute(
            select(WeakArea).where(
                WeakArea.user_id == user_id,
                WeakArea.goal_id == goal_id,
                WeakArea.topic == topic,
            )
        )
        weak = result.scalar_one_or_none()
        if weak:
            weak.occurrence_count += 1
            weak.last_seen_at = datetime.now(timezone.utc)
            weak.source = source
        else:
            weak = WeakArea(user_id=user_id, goal_id=goal_id, topic=topic, source=source)
            db.add(weak)
        results.append(weak)

    progress = await get_or_create_progress(db, user_id, goal_id)
    progress.weak_areas = [w.topic for w in results]
    await db.flush()
    return results


async def get_progress_summary(db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID | None) -> dict:
    progress_result = await db.execute(
        select(UserProgress).where(UserProgress.user_id == user_id).order_by(UserProgress.updated_at.desc())
    )
    all_progress = list(progress_result.scalars().all())
    progress = None
    if goal_id:
        progress = next((p for p in all_progress if p.goal_id == goal_id), None)
    if progress is None and all_progress:
        progress = all_progress[0]

    weak_result = await db.execute(
        select(WeakArea)
        .where(WeakArea.user_id == user_id)
        .order_by(WeakArea.occurrence_count.desc())
        .limit(10)
    )
    weak_areas = [
        {"topic": w.topic, "count": w.occurrence_count, "source": w.source}
        for w in weak_result.scalars().all()
    ]

    completion_pct = 0.0
    if goal_id:
        roadmap_result = await db.execute(
            select(Roadmap)
            .where(Roadmap.goal_id == goal_id, Roadmap.user_id == user_id, Roadmap.status == "active")
            .order_by(Roadmap.created_at.desc())
            .limit(1)
        )
        roadmap = roadmap_result.scalar_one_or_none()
        if roadmap:
            loaded = await load_roadmap_with_milestones(db, roadmap.id, user_id)
            if loaded:
                completion_pct = compute_completion_pct(loaded.milestone_rows)

    interview_result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.score.isnot(None))
        .order_by(InterviewSession.created_at.desc())
        .limit(5)
    )
    interviews = interview_result.scalars().all()

    return {
        "completion_pct": completion_pct,
        "total_study_hours": progress.total_study_hours if progress else 0.0,
        "completed_topics": progress.completed_topics if progress else [],
        "weak_areas": weak_areas,
        "current_week": progress.current_week if progress else None,
        "readiness_score": progress.readiness_score if progress else None,
        "last_interview_score": progress.last_interview_score if progress else None,
        "recent_interview_scores": [
            {"score": i.score, "role_context": i.role_context, "date": i.created_at.isoformat() if i.created_at else None}
            for i in interviews
        ],
    }
