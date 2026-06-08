import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, PointStruct
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.memory.qdrant_client import get_qdrant
from app.models import MemoryChunk
from app.services.llm import get_embeddings

settings = get_settings()


@lru_cache(maxsize=1)
def _embedding_cache_max() -> int:
    return settings.embedding_cache_size


# Session-level embedding cache: content hash -> vector
_embedding_cache: dict[str, list[float]] = {}


def _cache_get(text: str) -> list[float] | None:
    key = hashlib.sha256(text.encode()).hexdigest()
    return _embedding_cache.get(key)


def _cache_set(text: str, vector: list[float]) -> None:
    if len(_embedding_cache) >= _embedding_cache_max():
        _embedding_cache.pop(next(iter(_embedding_cache)))
    key = hashlib.sha256(text.encode()).hexdigest()
    _embedding_cache[key] = vector


async def embed_text(text: str) -> list[float]:
    cached = _cache_get(text)
    if cached is not None:
        return cached
    embeddings = get_embeddings()
    vector = await embeddings.aembed_query(text)
    _cache_set(text, vector)
    return vector


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed with cache lookup."""
    results: list[list[float] | None] = [None] * len(texts)
    to_embed: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        cached = _cache_get(text)
        if cached is not None:
            results[i] = cached
        else:
            to_embed.append((i, text))
    if to_embed:
        embeddings = get_embeddings()
        batch = await embeddings.aembed_documents([t[1] for t in to_embed])
        for (idx, text), vector in zip(to_embed, batch):
            results[idx] = vector
            _cache_set(text, vector)
    return [v or [] for v in results]


async def count_user_chunks(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(MemoryChunk).where(MemoryChunk.user_id == user_id)
    )
    return int(result.scalar_one())


class MemoryHit:
    def __init__(self, content: str, chunk_type: str, metadata: dict, score: float):
        self.content = content
        self.chunk_type = chunk_type
        self.metadata = metadata
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
            "score": self.score,
        }


class MemoryStore:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embeddings = get_embeddings()
        self.qdrant = get_qdrant()

    async def _embed(self, content: str) -> list[float]:
        return await embed_text(content)

    async def store_chunk(
        self,
        user_id: uuid.UUID,
        content: str,
        chunk_type: str,
        profile_id: uuid.UUID | None = None,
        goal_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        source_id: str | None = None,
        tags: list[str] | None = None,
        score: float | None = None,
        session_id: str | None = None,
        upsert: bool = False,
    ) -> MemoryChunk:
        meta = metadata or {}
        if upsert and source_id:
            existing = await self.db.execute(
                select(MemoryChunk).where(
                    MemoryChunk.user_id == user_id,
                    MemoryChunk.chunk_type == chunk_type,
                    MemoryChunk.source_id == source_id,
                )
            )
            chunk = existing.scalar_one_or_none()
            if chunk:
                chunk.content = content
                chunk.metadata_ = meta
                chunk.goal_id = goal_id
                embedding = await self._embed(content)
                await self._upsert_qdrant(
                    str(chunk.id), embedding, user_id, content, chunk_type, profile_id, goal_id, meta, tags, score, session_id
                )
                await self.db.flush()
                return chunk

        chunk_id = uuid.uuid4()
        embedding = await self._embed(content)

        chunk = MemoryChunk(
            id=chunk_id,
            user_id=user_id,
            profile_id=profile_id,
            goal_id=goal_id,
            content=content,
            chunk_type=chunk_type,
            source_id=source_id,
            metadata_=meta,
        )
        self.db.add(chunk)
        await self.db.flush()

        await self._upsert_qdrant(
            str(chunk_id), embedding, user_id, content, chunk_type, profile_id, goal_id, meta, tags, score, session_id
        )
        return chunk

    async def _upsert_qdrant(
        self,
        point_id: str,
        embedding: list[float],
        user_id: uuid.UUID,
        content: str,
        chunk_type: str,
        profile_id: uuid.UUID | None,
        goal_id: uuid.UUID | None,
        metadata: dict,
        tags: list[str] | None,
        score: float | None,
        session_id: str | None,
    ) -> None:
        await self.qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "user_id": str(user_id),
                        "profile_id": str(profile_id) if profile_id else None,
                        "goal_id": str(goal_id) if goal_id else None,
                        "chunk_type": chunk_type,
                        "content": content,
                        "metadata": metadata,
                        "tags": tags or [],
                        "score": score,
                        "session_id": session_id,
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ],
        )

    async def store_chunks_parallel(
        self,
        user_id: uuid.UUID,
        chunks: list[tuple[str, str, dict | None]],
        goal_id: uuid.UUID | None = None,
    ) -> list[MemoryChunk]:
        """Batch-embed and upsert multiple chunks concurrently."""
        if not chunks:
            return []

        contents = [c[0] for c in chunks]
        to_embed: list[tuple[int, str]] = []
        vectors: list[list[float] | None] = [None] * len(contents)
        for i, text in enumerate(contents):
            cached = _cache_get(text)
            if cached is not None:
                vectors[i] = cached
            else:
                to_embed.append((i, text))

        if to_embed:
            batch_vectors = await embed_texts([t[1] for t in to_embed])
            for (idx, _), vector in zip(to_embed, batch_vectors):
                vectors[idx] = vector

        results: list[MemoryChunk] = []
        qdrant_tasks = []
        for i, (content, chunk_type, metadata) in enumerate(chunks):
            chunk_id = uuid.uuid4()
            meta = metadata or {}
            chunk = MemoryChunk(
                id=chunk_id,
                user_id=user_id,
                goal_id=goal_id,
                content=content,
                chunk_type=chunk_type,
                metadata_=meta,
            )
            self.db.add(chunk)
            results.append(chunk)
            qdrant_tasks.append(
                self._upsert_qdrant(
                    str(chunk_id),
                    vectors[i] or [],
                    user_id,
                    content,
                    chunk_type,
                    None,
                    goal_id,
                    meta,
                    None,
                    None,
                    None,
                )
            )
        await self.db.flush()
        await asyncio.gather(*qdrant_tasks)
        return results

    async def store_chunks(
        self,
        user_id: uuid.UUID,
        chunks: list[tuple[str, str, dict | None]],
        profile_id: uuid.UUID | None = None,
        goal_id: uuid.UUID | None = None,
    ) -> list[MemoryChunk]:
        results = []
        for content, chunk_type, metadata in chunks:
            chunk = await self.store_chunk(
                user_id, content, chunk_type, profile_id=profile_id, goal_id=goal_id, metadata=metadata
            )
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
        goal_id: uuid.UUID | None = None,
        limit: int = 8,
    ) -> list[MemoryHit]:
        query_embedding = await embed_text(query)

        must_conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
        ]
        if chunk_types:
            must_conditions.append(
                FieldCondition(key="chunk_type", match=MatchAny(any=chunk_types))
            )
        if goal_id:
            must_conditions.append(
                FieldCondition(key="goal_id", match=MatchValue(value=str(goal_id)))
            )

        response = await self.qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=query_embedding,
            query_filter=Filter(must=must_conditions),
            limit=limit,
        )
        hits = []
        for point in response.points:
            if not point.payload:
                continue
            hits.append(
                MemoryHit(
                    content=point.payload.get("content", ""),
                    chunk_type=point.payload.get("chunk_type", ""),
                    metadata=point.payload.get("metadata", {}),
                    score=point.score or 0.0,
                )
            )
        return hits

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
