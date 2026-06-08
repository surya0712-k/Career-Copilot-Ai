import json
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import ROADMAP_PROMPT, ROADMAP_RECALC_PROMPT
from app.memory.retriever import build_rag_context, format_rag_context
from app.memory.store import MemoryStore, count_user_chunks
from app.memory.types import ROADMAP_UPDATE
from app.models import Goal, Milestone, Profile, Roadmap
from app.services.llm import get_llm
from app.config import get_settings
from app.observability.timing import timed_step
from app.services.progress_service import get_progress_summary
from app.services.prompt_context import build_roadmap_llm_payload
from app.services.roadmap_utils import (
    load_roadmap_with_milestones,
    normalize_milestone_weeks,
    normalize_task,
    sync_roadmap_jsonb,
)

settings = get_settings()


class RoadmapTaskOutput(BaseModel):
    title: str = Field(max_length=80)
    description: str = Field(default="", max_length=200)
    task_type: str = Field(default="practice", pattern="^(practice|project)$")


class MilestoneOutput(BaseModel):
    title: str = Field(max_length=80)
    description: str = Field(default="", max_length=200)
    week_start: int = Field(default=1, ge=1, le=52)
    week_end: int = Field(default=2, ge=1, le=52)
    tasks: list[RoadmapTaskOutput] = Field(default_factory=list, max_length=3)
    success_criteria: str = Field(default="", max_length=200)


class RoadmapOutput(BaseModel):
    title: str = Field(max_length=100)
    milestones: list[MilestoneOutput] = Field(default_factory=list, max_length=4)


class RoadmapService:
    async def generate_initial(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        target_company: str,
        target_role: str,
        level: str,
        gap_analysis: dict,
    ) -> dict[str, Any]:
        async with timed_step(None, "roadmap.generate_initial"):
            query = f"{target_company} {target_role}"
            chunk_count = await count_user_chunks(db, user_id)
            memories: list[str] = []
            if chunk_count > 3:
                async with timed_step(None, "roadmap.rag"):
                    memories = await build_rag_context(db, user_id, query, limit=5)

            profile_result = await db.execute(select(Profile).where(Profile.user_id == user_id))
            profile = profile_result.scalar_one_or_none()
            dsa_language = (profile.preferred_dsa_language if profile else None) or "python"

            llm = get_llm().bind(max_tokens=settings.llm_onboarding_max_tokens)
            structured_llm = llm.with_structured_output(RoadmapOutput)
            target = f"{target_company} {target_role} ({level})"
            payload = build_roadmap_llm_payload(
                gap_analysis=gap_analysis,
                target=target,
                memory=await format_rag_context(memories),
                dsa_language=dsa_language,
            )
            async with timed_step(None, "roadmap.llm"):
                result: RoadmapOutput = await structured_llm.ainvoke(
                    [
                        SystemMessage(content=ROADMAP_PROMPT),
                        HumanMessage(content=payload),
                    ]
                )
            roadmap = result.model_dump()
            for milestone in roadmap.get("milestones", []):
                for task in milestone.get("tasks", []):
                    task.setdefault("resources", [])
            normalize_milestone_weeks(roadmap.get("milestones", []))
            return roadmap

    async def persist_roadmap(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        roadmap_data: dict,
        version: int = 1,
        supersedes_id: uuid.UUID | None = None,
        write_memory: bool = True,
    ) -> Roadmap:
        roadmap = Roadmap(
            user_id=user_id,
            goal_id=goal_id,
            title=roadmap_data.get("title", "Career Roadmap"),
            status="active",
            version=version,
            supersedes_id=supersedes_id,
        )
        db.add(roadmap)
        await db.flush()

        milestones = normalize_milestone_weeks(list(roadmap_data.get("milestones", [])))
        for m in milestones:
            tasks = []
            for t in m.get("tasks", []):
                task = normalize_task(t)
                tasks.append(task)
            milestone = Milestone(
                roadmap_id=roadmap.id,
                title=m.get("title", ""),
                description=m.get("description"),
                week_start=m.get("week_start"),
                week_end=m.get("week_end"),
                status="pending",
                tasks=tasks,
            )
            db.add(milestone)

        await db.flush()
        await db.refresh(roadmap)
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(Roadmap).where(Roadmap.id == roadmap.id).options(selectinload(Roadmap.milestone_rows))
        )
        roadmap = result.scalar_one()
        sync_roadmap_jsonb(roadmap)

        if write_memory and not settings.defer_memory_writes:
            store = MemoryStore(db)
            milestone_summaries = [
                f"Week {m.get('week_start')}-{m.get('week_end')}: {m.get('title')}"
                for m in roadmap_data.get("milestones", [])
            ]
            content = f"Roadmap v{version} '{roadmap_data.get('title', '')}': " + "; ".join(milestone_summaries)
            await store.store_chunk(
                user_id,
                content,
                ROADMAP_UPDATE,
                goal_id=goal_id,
                metadata={"roadmap": roadmap_data, "version": version},
                source_id=str(roadmap.id),
                upsert=True,
            )
        return roadmap

    async def recalculate(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        roadmap_id: uuid.UUID,
    ) -> Roadmap:
        roadmap = await load_roadmap_with_milestones(db, roadmap_id, user_id)
        if roadmap is None:
            raise ValueError("Roadmap not found")

        profile_result = await db.execute(select(Profile).where(Profile.user_id == user_id))
        profile = profile_result.scalar_one_or_none()
        gap_analysis = profile.gap_analysis if profile else {}

        progress = await get_progress_summary(db, user_id, roadmap.goal_id)
        completed_milestones = []
        remaining_context = []
        for m in roadmap.milestone_rows:
            tasks = [normalize_task(t) for t in (m.tasks or [])]
            if all(t.get("completed") for t in tasks) and tasks:
                completed_milestones.append(milestone_row_to_dict_local(m))
            else:
                remaining_context.append(
                    {
                        "title": m.title,
                        "week_start": m.week_start,
                        "pending_tasks": [t for t in tasks if not t.get("completed")],
                    }
                )

        goal_result = await db.execute(select(Goal).where(Goal.id == roadmap.goal_id))
        goal = goal_result.scalar_one_or_none()
        memories = await build_rag_context(
            db, user_id, "interview weaknesses progress roadmap", limit=15
        )

        llm = get_llm()
        structured_llm = llm.with_structured_output(RoadmapOutput)
        dsa_language = (profile.preferred_dsa_language if profile else None) or "python"
        from app.services.prompt_context import DSA_LANGUAGE_LABELS

        context = {
            "gap_analysis": gap_analysis,
            "progress": progress,
            "completed_milestones": completed_milestones,
            "remaining": remaining_context,
            "weak_areas": progress.get("weak_areas", []),
            "memory": await format_rag_context(memories),
            "target": f"{goal.target_company} {goal.target_role} ({goal.level})" if goal else "",
            "dsa_language": DSA_LANGUAGE_LABELS.get(dsa_language, dsa_language),
        }
        result: RoadmapOutput = await structured_llm.ainvoke(
            [
                SystemMessage(content=ROADMAP_RECALC_PROMPT),
                HumanMessage(content=json.dumps(context, indent=2)[:12000]),
            ]
        )
        new_data = result.model_dump()
        for milestone in new_data.get("milestones", []):
            for task in milestone.get("tasks", []):
                task.setdefault("resources", [])

        merged_milestones = completed_milestones + [
            {
                **m.model_dump(),
                "tasks": [normalize_task(t.model_dump()) for t in m.tasks],
                "status": "pending",
            }
            for m in result.milestones
        ]
        new_data["milestones"] = normalize_milestone_weeks(merged_milestones)

        roadmap.status = "superseded"
        return await self.persist_roadmap(
            db,
            user_id,
            roadmap.goal_id,
            new_data,
            version=roadmap.version + 1,
            supersedes_id=roadmap.id,
        )


def milestone_row_to_dict_local(m: Milestone) -> dict:
    from app.services.roadmap_utils import milestone_row_to_dict

    d = milestone_row_to_dict(m)
    d["status"] = "completed"
    return d
