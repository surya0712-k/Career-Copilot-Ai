import uuid
from typing import Any

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import COACH_PROMPT
from app.memory.retriever import build_rag_hits
from app.memory.store import MemoryStore
from app.memory.types import INTERVIEW_CHUNK_TYPES, INTERVIEW_WEAKNESS, USER_NOTE
from app.models import WeakArea
from app.services.llm import get_llm
from app.services.progress_service import get_progress_summary


class MemoryService:
    async def save(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        content: str,
        chunk_type: str,
        goal_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        source_id: str | None = None,
        upsert: bool = False,
    ) -> dict[str, Any]:
        store = MemoryStore(db)
        chunk = await store.store_chunk(
            user_id,
            content,
            chunk_type,
            goal_id=goal_id,
            metadata=metadata,
            source_id=source_id,
            upsert=upsert,
        )
        return {"id": str(chunk.id), "chunk_type": chunk.chunk_type, "content": chunk.content}

    async def retrieve(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        chunk_types: list[str] | None = None,
        goal_id: uuid.UUID | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        hits = await build_rag_hits(db, user_id, query, chunk_types, goal_id, limit)
        return [h.to_dict() for h in hits]

    async def save_note(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        content: str,
        goal_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        return await self.save(db, user_id, content, USER_NOTE, goal_id=goal_id)

    async def ask(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question: str,
        goal_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        chunk_types = None
        q_lower = question.lower()
        if "weakness" in q_lower or "interview" in q_lower:
            chunk_types = INTERVIEW_CHUNK_TYPES + [INTERVIEW_WEAKNESS]

        async def fetch_hits():
            return await build_rag_hits(db, user_id, question, chunk_types, goal_id, limit=8)

        async def fetch_progress():
            return await get_progress_summary(db, user_id, goal_id)

        async def fetch_weak():
            weak_result = await db.execute(
                select(WeakArea)
                .where(WeakArea.user_id == user_id)
                .order_by(WeakArea.occurrence_count.desc())
                .limit(8)
            )
            return [
                {"topic": w.topic, "occurrence_count": w.occurrence_count, "source": w.source}
                for w in weak_result.scalars().all()
            ]

        hits, progress, weak_stats = await asyncio.gather(fetch_hits(), fetch_progress(), fetch_weak())

        memory_text = "\n".join(
            f"[{h.chunk_type}]: {h.content[:400]}" for h in hits
        )
        llm = get_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(content=COACH_PROMPT),
                HumanMessage(
                    content=(
                        f"Question: {question}\n\n"
                        f"Progress: {progress}\n\n"
                        f"Weak areas: {weak_stats}\n\n"
                        f"Memory:\n{memory_text}"
                    )
                ),
            ]
        )
        return {
            "answer": response.content,
            "citations": [h.to_dict() for h in hits[:5]],
            "weak_area_stats": weak_stats,
            "progress": progress,
        }
