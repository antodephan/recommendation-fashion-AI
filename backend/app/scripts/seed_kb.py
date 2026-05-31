"""Seed the fashion knowledge base in Qdrant (RAG source)."""

from __future__ import annotations

import uuid

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import embed_texts
from ai_engine.vector_store import ensure_collections, get_qdrant, upsert_points

KB_DOCS = [
    {
        "title": "Dressing for an Hourglass Body",
        "text": (
            "Hourglass body types benefit from fitted clothing that emphasizes the waist. "
            "Wrap dresses, high-waisted bottoms, and tailored jackets work beautifully. "
            "Avoid shapeless silhouettes."
        ),
    },
    {
        "title": "Color Theory for Warm Skin Tones",
        "text": (
            "Warm undertones flatter earth tones: olive, mustard, terracotta, camel, cream, gold. "
            "Avoid cool icy pastels next to the face."
        ),
    },
    {
        "title": "Fabric Care for Wool",
        "text": (
            "Wool benefits from dry cleaning or hand washing in cold water with wool-friendly detergent. "
            "Lay flat to dry to maintain shape; avoid hanging wet wool garments."
        ),
    },
    {
        "title": "Capsule Wardrobe Essentials",
        "text": (
            "A capsule wardrobe relies on 30 well-chosen pieces — neutral palette, mix-and-match basics, "
            "one statement coat, two quality shoes (sneakers + boots), a tailored blazer."
        ),
    },
    {
        "title": "Layering in Cold Weather",
        "text": (
            "Effective cold-weather layering: moisture-wicking base, insulating mid-layer (wool/down), "
            "windproof shell. Use lighter layers for mobility, heavier for static cold."
        ),
    },
    {
        "title": "Sustainable Fashion Basics",
        "text": (
            "Sustainable choices favor natural fibers (organic cotton, linen, wool), deadstock fabrics, "
            "and circular brands. Prefer 'cost per wear' over fast trends."
        ),
    },
    {
        "title": "Smart-Casual Office Dress Code",
        "text": (
            "Smart-casual office: tailored chinos or wool trousers, polished leather sneakers or loafers, "
            "a refined knit or button-up shirt, optional unstructured blazer."
        ),
    },
    {
        "title": "Petite Styling Tips",
        "text": (
            "Petite figures benefit from monochrome looks, vertical lines, high-waisted bottoms, "
            "cropped jackets and pointed-toe shoes — all elongate the silhouette."
        ),
    },
]


async def seed_knowledge_base() -> None:
    await ensure_collections()
    client = get_qdrant()
    try:
        info = await client.count(collection_name=settings.QDRANT_COLLECTION_KB, exact=True)
        existing_count = int(getattr(info, "count", 0) or 0)
    except Exception:
        existing_count = 0
    if existing_count > 0:
        logger.info(f"Knowledge base already has {existing_count} docs; skipping.")
        return

    texts = [f"{d['title']}\n\n{d['text']}" for d in KB_DOCS]
    vectors = await embed_texts(texts)
    points = [
        (
            str(uuid.uuid4()),
            vec,
            {"title": d["title"], "text": text, "source": "couture-kb"},
        )
        for d, vec, text in zip(KB_DOCS, vectors, texts)
    ]
    await upsert_points(settings.QDRANT_COLLECTION_KB, points)
    logger.info(f"Seeded {len(KB_DOCS)} knowledge-base docs in Qdrant")
