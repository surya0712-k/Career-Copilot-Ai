"""Helpers for roadmap milestone sync between relational rows and JSONB snapshot."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Milestone, Roadmap

TaskType = Literal["practice", "project"]


def infer_task_type(task: dict | str) -> TaskType:
    if isinstance(task, str):
        return "practice"
    explicit = task.get("task_type")
    if explicit in ("practice", "project"):
        return explicit

    title = task.get("title", "")
    desc = task.get("description", "")
    text = f"{title} {desc}".lower()

    if re.search(r"^project\s*\d+\s*:", title, re.I):
        return "project"

    if re.search(
        r"leetcode|solve \d+|timed practice|practice session|\bmediums?\b|mock interview|study |read |chapters?",
        text,
    ):
        return "practice"

    if re.match(r"^(build|create|develop|deploy)\s", title, re.I):
        return "project"

    if re.match(r"^add\s", title, re.I) and re.search(
        r"load test|metrics|monitoring|url shortener|backend|service|api", text
    ):
        return "project"

    if re.search(
        r"load test|load testing|url shortener|backend service|scalable|microservice|rest api|fastapi service|metrics",
        text,
    ) and not re.search(r"implement solutions|leetcode|solve \d+", text):
        return "project"

    return "practice"


def clean_milestone_title(title: str) -> str:
    cleaned = re.sub(r"^week\s*\d+\s*:\s*", "", title, flags=re.I).strip()
    return cleaned or title


def normalize_milestone_weeks(
    milestones: list[dict[str, Any]], start_week: int = 1
) -> list[dict[str, Any]]:
    """Force sequential week numbers so milestone 1 is always Week 1."""
    for i, m in enumerate(milestones):
        week = start_week + i
        m["week_start"] = week
        m["week_end"] = week
        if title := m.get("title"):
            m["title"] = clean_milestone_title(str(title))
    return milestones


def normalize_task(task: dict | str) -> dict[str, Any]:
    if isinstance(task, str):
        normalized = {
            "title": task,
            "description": "",
            "resources": [],
            "completed": False,
            "completed_at": None,
        }
        normalized["task_type"] = infer_task_type(normalized)
        return normalized
    normalized = {
        "title": task.get("title", ""),
        "description": task.get("description", ""),
        "resources": task.get("resources", []),
        "completed": bool(task.get("completed", False)),
        "completed_at": task.get("completed_at"),
        "task_type": infer_task_type(task),
    }
    return normalized


def milestone_row_to_dict(m: Milestone, *, display_week: int | None = None) -> dict[str, Any]:
    tasks = [normalize_task(t) for t in (m.tasks or [])]
    week = display_week if display_week is not None else m.week_start
    week_end = display_week if display_week is not None else m.week_end
    return {
        "id": str(m.id),
        "title": clean_milestone_title(m.title or ""),
        "description": m.description,
        "week_start": week,
        "week_end": week_end,
        "status": m.status,
        "tasks": tasks,
        "success_criteria": "",
    }


def sync_roadmap_jsonb(roadmap: Roadmap) -> None:
    """Update JSONB snapshot from relational milestone rows with sequential week numbers."""
    sorted_rows = sorted(roadmap.milestone_rows, key=lambda x: (x.week_start or 0, str(x.id)))
    roadmap.milestones = [
        milestone_row_to_dict(m, display_week=i + 1) for i, m in enumerate(sorted_rows)
    ]


async def load_roadmap_with_milestones(
    db: AsyncSession, roadmap_id: uuid.UUID, user_id: uuid.UUID
) -> Roadmap | None:
    from sqlalchemy import select

    result = await db.execute(
        select(Roadmap)
        .where(Roadmap.id == roadmap_id, Roadmap.user_id == user_id)
        .options(selectinload(Roadmap.milestone_rows))
    )
    roadmap = result.scalar_one_or_none()
    if roadmap:
        sync_roadmap_jsonb(roadmap)
    return roadmap


def compute_completion_pct(milestones: list[Milestone]) -> float:
    total = 0
    done = 0
    for m in milestones:
        for t in m.tasks or []:
            task = normalize_task(t)
            total += 1
            if task.get("completed"):
                done += 1
    return round((done / total) * 100, 1) if total else 0.0
