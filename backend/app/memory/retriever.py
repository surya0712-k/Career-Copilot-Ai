import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.store import MemoryHit, MemoryRetriever


async def build_rag_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    chunk_types: list[str] | None = None,
    goal_id: uuid.UUID | None = None,
    limit: int = 8,
) -> list[str]:
    retriever = MemoryRetriever(db)
    hits = await retriever.retrieve(user_id, query, chunk_types, goal_id, limit)
    return [h.content for h in hits]


async def build_rag_hits(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    chunk_types: list[str] | None = None,
    goal_id: uuid.UUID | None = None,
    limit: int = 8,
) -> list[MemoryHit]:
    retriever = MemoryRetriever(db)
    return await retriever.retrieve(user_id, query, chunk_types, goal_id, limit)


async def format_rag_context(memories: list[str]) -> str:
    if not memories:
        return "No prior context available."
    return "\n---\n".join(f"- {m}" for m in memories)
