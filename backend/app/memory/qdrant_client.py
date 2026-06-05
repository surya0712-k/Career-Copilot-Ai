from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    VectorParams,
)

from app.config import get_settings

settings = get_settings()
VECTOR_SIZE = 1536


@lru_cache
def get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


async def ensure_collection() -> None:
    client = get_qdrant()
    collection = settings.qdrant_collection

    collections = await client.get_collections()
    exists = any(c.name == collection for c in collections.collections)

    if not exists:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        await client.create_payload_index(
            collection_name=collection,
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await client.create_payload_index(
            collection_name=collection,
            field_name="chunk_type",
            field_schema=PayloadSchemaType.KEYWORD,
        )
