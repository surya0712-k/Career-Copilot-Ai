import uuid

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, PointStruct
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.memory.qdrant_client import get_qdrant
from app.models import MemoryChunk
from app.services.llm import get_embeddings

settings = get_settings()


class MemoryStore:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embeddings = get_embeddings()
        self.qdrant = get_qdrant()

    async def store_chunk(
        self,
        user_id: uuid.UUID,
        content: str,
        chunk_type: str,
        profile_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> MemoryChunk:
        chunk_id = uuid.uuid4()
        embedding = await self.embeddings.aembed_query(content)

        chunk = MemoryChunk(
            id=chunk_id,
            user_id=user_id,
            profile_id=profile_id,
            content=content,
            chunk_type=chunk_type,
            metadata_=metadata or {},
        )
        self.db.add(chunk)
        await self.db.flush()

        await self.qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=str(chunk_id),
                    vector=embedding,
                    payload={
                        "user_id": str(user_id),
                        "profile_id": str(profile_id) if profile_id else None,
                        "chunk_type": chunk_type,
                        "content": content,
                        "metadata": metadata or {},
                    },
                )
            ],
        )
        return chunk

    async def store_chunks(
        self,
        user_id: uuid.UUID,
        chunks: list[tuple[str, str, dict | None]],
        profile_id: uuid.UUID | None = None,
    ) -> list[MemoryChunk]:
        results = []
        for content, chunk_type, metadata in chunks:
            chunk = await self.store_chunk(user_id, content, chunk_type, profile_id, metadata)
            results.append(chunk)
        return results


class MemoryRetriever:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embeddings = get_embeddings()
        self.qdrant = get_qdrant()

    async def retrieve(
        self,
        user_id: uuid.UUID,
        query: str,
        chunk_types: list[str] | None = None,
        limit: int = 8,
    ) -> list[str]:
        query_embedding = await self.embeddings.aembed_query(query)

        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
        ]
        if chunk_types:
            must_conditions.append(
                FieldCondition(key="chunk_type", match=MatchAny(any=chunk_types))
            )

        results = await self.qdrant.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_embedding,
            query_filter=Filter(must=must_conditions),
            limit=limit,
        )
        return [hit.payload.get("content", "") for hit in results if hit.payload]

    async def get_recent_by_type(
        self,
        user_id: uuid.UUID,
        chunk_type: str,
        limit: int = 5,
    ) -> list[MemoryChunk]:
        result = await self.db.execute(
            select(MemoryChunk)
            .where(MemoryChunk.user_id == user_id, MemoryChunk.chunk_type == chunk_type)
            .order_by(MemoryChunk.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
