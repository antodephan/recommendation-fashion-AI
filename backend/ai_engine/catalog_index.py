"""Index outfit rows into Qdrant (shared by seed + CSV import)."""

from __future__ import annotations

from typing import Iterable

from app.config import settings
from app.core.logger import logger
from app.models.outfit import Outfit

from ai_engine.embeddings import embed_texts
from ai_engine.recommender import outfit_to_index_text
from ai_engine.vector_store import ensure_collections, upsert_points


async def index_outfits_to_qdrant(outfits: Iterable[Outfit], *, batch_size: int = 64) -> int:
    """Embed and upsert outfits into the Qdrant `outfits` collection."""
    outfit_list = list(outfits)
    if not outfit_list:
        return 0

    await ensure_collections()
    indexed = 0

    for start in range(0, len(outfit_list), batch_size):
        chunk = outfit_list[start : start + batch_size]
        texts = [outfit_to_index_text(o) for o in chunk]
        vectors = await embed_texts(texts)
        points = [
            (
                str(o.id),
                vec,
                {
                    "name": o.name,
                    "style": o.style,
                    "season": o.season,
                    "gender": o.gender,
                    "occasion": o.occasion,
                    "tags": o.tags or [],
                    "colors": o.colors or [],
                    "catalog_id": (o.meta or {}).get("catalog_id"),
                    "hm_product_id": (o.meta or {}).get("hm_product_id"),
                    "brand": o.brand or "H&M",
                    "price": o.price,
                    "region": (o.meta or {}).get("region"),
                    "text": text,
                },
            )
            for o, vec, text in zip(chunk, vectors, texts)
        ]
        await upsert_points(settings.QDRANT_COLLECTION_OUTFITS, points)
        indexed += len(chunk)
        logger.info(f"Indexed {indexed}/{len(outfit_list)} outfits in Qdrant")

    return indexed
