"""Qdrant vector store wrapper used across recommendation + RAG."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from app.config import settings
from app.core.logger import logger

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
            prefer_grpc=False,
        )
    return _client


@dataclass
class VectorHit:
    id: str
    score: float
    payload: dict[str, Any]


COLLECTIONS = (
    settings.QDRANT_COLLECTION_OUTFITS,
    settings.QDRANT_COLLECTION_PRODUCTS,
    settings.QDRANT_COLLECTION_USERS,
    settings.QDRANT_COLLECTION_CHATS,
    settings.QDRANT_COLLECTION_KB,
)


async def ensure_collections(dim: int | None = None) -> None:
    """Create all required collections if absent."""
    dim = dim or settings.EMBEDDING_DIM
    client = get_qdrant()
    existing = {c.name for c in (await client.get_collections()).collections}
    for name in COLLECTIONS:
        if name not in existing:
            logger.info(f"Creating Qdrant collection '{name}' (dim={dim})")
            await client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )


async def upsert_points(
    collection: str,
    points: Iterable[tuple[str | uuid.UUID, list[float], dict[str, Any]]],
) -> None:
    client = get_qdrant()
    structs = [
        qm.PointStruct(id=str(pid), vector=vec, payload=payload)
        for pid, vec, payload in points
    ]
    if not structs:
        return
    await client.upsert(collection_name=collection, points=structs)


async def search(
    collection: str,
    vector: list[float],
    top_k: int = 10,
    filter_payload: dict[str, Any] | None = None,
) -> list[VectorHit]:
    """Vector similarity search with optional metadata filter."""
    client = get_qdrant()
    qfilter = None
    if filter_payload:
        must = [
            qm.FieldCondition(key=k, match=qm.MatchValue(value=v))
            for k, v in filter_payload.items()
            if v is not None
        ]
        if must:
            qfilter = qm.Filter(must=must)
    try:
        result = await client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            query_filter=qfilter,
            with_payload=True,
        )
    except Exception as exc:
        logger.warning(f"Qdrant search failed for '{collection}': {exc}")
        return []
    return [VectorHit(id=str(p.id), score=float(p.score), payload=p.payload or {}) for p in result]


async def delete_point(collection: str, point_id: str | uuid.UUID) -> None:
    client = get_qdrant()
    await client.delete(
        collection_name=collection,
        points_selector=qm.PointIdsList(points=[str(point_id)]),
    )


async def get_user_profile_vector(user_id: str) -> list[float] | None:
    client = get_qdrant()
    try:
        res = await client.retrieve(
            collection_name=settings.QDRANT_COLLECTION_USERS,
            ids=[str(user_id)],
            with_vectors=True,
        )
    except Exception:
        return None
    if not res:
        return None
    return res[0].vector  # type: ignore[return-value]
