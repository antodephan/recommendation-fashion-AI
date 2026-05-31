"""Seed editorial fashion trends."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logger import logger
from app.database import AsyncSessionLocal
from app.models.trend import FashionTrend


SEED = [
    {
        "title": "Quiet Luxury Returns",
        "summary": "Refined neutrals, premium fabrics, and zero logos define this season's discreet wealth aesthetic.",
        "content": "Quiet luxury favors craftsmanship over conspicuous branding. Think cashmere knits, cream tailoring, and supple leather.",
        "image_url": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=900",
        "source": "Vogue Editorial",
        "season": "winter",
        "tags": ["quiet-luxury", "minimalism", "neutrals"],
        "popularity": 0.92,
    },
    {
        "title": "Tech-Wear Goes Mainstream",
        "summary": "Technical fabrics, modular straps and utility silhouettes spill from runways into daily wardrobes.",
        "content": "Brands are blending sportswear functionality with sharp tailoring — water-resistant trenches, modular vests, magnetic closures.",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=900",
        "source": "Hypebeast",
        "season": "spring",
        "tags": ["techwear", "utility", "modular"],
        "popularity": 0.81,
    },
    {
        "title": "Bold Color Blocking",
        "summary": "Saturated reds, electric blues and acid greens combine in unexpected pairings.",
        "content": "Designers are layering primary colors with no neutrals to break the look — full looks in clashing hues.",
        "image_url": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=900",
        "source": "Business of Fashion",
        "season": "summer",
        "tags": ["color-blocking", "bold", "playful"],
        "popularity": 0.74,
    },
    {
        "title": "Y2K Revival",
        "summary": "Low-rise jeans, baby tees, butterfly motifs and tinted sunglasses make a confident comeback.",
        "content": "Gen Z is rebuilding the early 2000s aesthetic with modern silhouettes and sustainable fabrics.",
        "image_url": "https://images.unsplash.com/photo-1521223890158-f9f7c3d5d504?w=900",
        "source": "i-D Magazine",
        "season": "spring",
        "tags": ["y2k", "nostalgia", "playful"],
        "popularity": 0.86,
    },
]


async def seed_trends() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(FashionTrend).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("Trends already seeded; skipping.")
            return
        now = datetime.now(timezone.utc)
        for spec in SEED:
            db.add(FashionTrend(published_at=now, **spec))
        await db.commit()
        logger.info(f"Seeded {len(SEED)} trends")
