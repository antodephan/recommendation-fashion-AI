"""Sync seasonal style trends from vector DB + catalog signals; index to fashion_kb."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.core.logger import configure_logging, logger
from app.database import AsyncSessionLocal
from app.models.sync_run import SyncJobType
from app.models.trend import FashionTrend
from app.services.analytics_service import AnalyticsService
from app.services.season_service import infer_season
from app.services.sync_run_service import finalize_sync_run, sync_run_context
from app.services.trend_service import TrendService

from ai_engine.embeddings import embed_texts
from ai_engine.vector_store import ensure_collections, upsert_points

# Editorial style cards — H&M products loaded only when user clicks a trend.
STYLE_CATALOG: list[dict] = [
    {
        "title": "Quiet Luxury",
        "summary": "Neutrals, premium knits and clean tailoring — understated pieces many wardrobes are leaning toward this season.",
        "image_url": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=900",
        "tags": ["minimalist", "neutrals", "tailoring", "quiet-luxury"],
        "style_type": "minimalist",
        "sections": ["ladies", "men"],
        "seasons": ["winter", "autumn", "all"],
        "base_popularity": 0.88,
    },
    {
        "title": "Coastal Casual",
        "summary": "Breathable linen, relaxed shirts and light layers — a go-to look when temperatures rise and outdoor plans pick up.",
        "image_url": "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=900",
        "tags": ["linen", "casual", "summer", "resort", "coastal"],
        "style_type": "casual",
        "sections": ["ladies", "men"],
        "seasons": ["summer", "spring"],
        "base_popularity": 0.84,
    },
    {
        "title": "Office Smart-Casual",
        "summary": "Blazers with soft trousers and polished basics — the hybrid uniform dominating weekday outfits.",
        "image_url": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=900",
        "tags": ["smart-casual", "office", "blazer", "workwear"],
        "style_type": "smart-casual",
        "sections": ["ladies", "men"],
        "seasons": ["spring", "autumn", "all"],
        "base_popularity": 0.86,
    },
    {
        "title": "Streetwear Utility",
        "summary": "Oversized silhouettes, cargo details and sneakers — urban comfort that keeps trending across age groups.",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=900",
        "tags": ["streetwear", "utility", "sneakers", "oversized"],
        "style_type": "streetwear",
        "sections": ["men", "ladies"],
        "seasons": ["spring", "autumn", "all"],
        "base_popularity": 0.82,
    },
    {
        "title": "Soft Romantic",
        "summary": "Flowing fabrics, pastel tones and delicate layers — feminine dressing with high repeat-wear appeal.",
        "image_url": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=900",
        "tags": ["romantic", "pastel", "dress", "feminine"],
        "style_type": "romantic",
        "sections": ["ladies"],
        "seasons": ["spring", "summer"],
        "base_popularity": 0.79,
    },
    {
        "title": "Monochrome Minimal",
        "summary": "Head-to-toe black, white and grey — high-contrast outfits that stay among the most saved looks.",
        "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=900",
        "tags": ["monochrome", "minimalist", "black", "white"],
        "style_type": "minimalist",
        "sections": ["ladies", "men"],
        "seasons": ["all"],
        "base_popularity": 0.9,
    },
    {
        "title": "Cozy Layering",
        "summary": "Chunky knits, long coats and warm accessories — layered outfits built for cooler months.",
        "image_url": "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?w=900",
        "tags": ["layering", "knit", "coat", "winter", "cozy"],
        "style_type": "casual",
        "sections": ["ladies", "men"],
        "seasons": ["winter", "autumn"],
        "base_popularity": 0.87,
    },
    {
        "title": "Sporty Athleisure",
        "summary": "Performance fabrics meeting everyday wear — joggers, hoodies and clean trainers everywhere.",
        "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=900",
        "tags": ["athleisure", "sportswear", "hoodie", "joggers"],
        "style_type": "athleisure",
        "sections": ["ladies", "men", "sportswear"],
        "seasons": ["all"],
        "base_popularity": 0.83,
    },
    {
        "title": "Y2K Revival",
        "summary": "Low-rise silhouettes, baby tees and bold accessories — nostalgic energy still climbing in search interest.",
        "image_url": "https://images.unsplash.com/photo-1521223890158-f9f7c3d5d504?w=900",
        "tags": ["y2k", "nostalgia", "playful", "retro"],
        "style_type": "y2k",
        "sections": ["ladies"],
        "seasons": ["spring", "summer"],
        "base_popularity": 0.8,
    },
    {
        "title": "Earth-Tone Capsule",
        "summary": "Camel, olive, rust and cream — warm naturals forming cohesive capsule wardrobes.",
        "image_url": "https://images.unsplash.com/photo-1483985988354-763728e1935b?w=900",
        "tags": ["earth-tone", "capsule", "camel", "olive", "autumn"],
        "style_type": "capsule",
        "sections": ["ladies", "men"],
        "seasons": ["autumn", "winter"],
        "base_popularity": 0.85,
    },
]


def _score_style(spec: dict, signals: dict[str, float], season: str) -> float:
    score = float(spec.get("base_popularity", 0.5))
    seasons = spec.get("seasons") or ["all"]
    if season in seasons or "all" in seasons:
        score += 0.08
    else:
        score -= 0.15
    for tag in spec.get("tags") or []:
        score += min(0.25, signals.get(str(tag).lower(), 0) * 0.12)
    style_type = str(spec.get("style_type", "")).lower()
    if style_type:
        score += min(0.2, signals.get(style_type, 0) * 0.15)
    return min(1.0, max(0.1, score))


async def _resolve_hm_categories(section: str) -> list[str]:
    """Best-effort category hints for lazy H&M fetch (stored in trend.extra)."""
    try:
        from app.services.hm_client import HMClient

        client = HMClient()
        region = await client.resolve_region(settings.HM_REGION)
        cats = await client.list_categories(region)
        section = section.lower()
        matched = [
            c["category_id"]
            for c in cats
            if section in c.get("category_id", "").lower()
            and any(k in c["category_id"].lower() for k in ("newarrivals", "viewall", "shopbyproduct"))
        ]
        if matched:
            return matched[:4]
        fallback = [c["category_id"] for c in cats if section in c.get("category_id", "").lower()]
        return fallback[:3] or [c["category_id"] for c in cats[:2]]
    except Exception as exc:
        logger.debug(f"H&M category hints skipped: {exc}")
        return []


async def _index_trends_to_kb(trends: list[FashionTrend]) -> int:
    if not trends:
        return 0
    await ensure_collections()
    texts = [f"{t.title}\n\n{t.summary}" for t in trends]
    vectors = await embed_texts(texts)
    points = [
        (
            str(t.id),
            vec,
            {
                "title": t.title,
                "text": text,
                "source": "style-trend",
                "season": t.season,
                "tags": t.tags,
            },
        )
        for t, vec, text in zip(trends, vectors, texts)
    ]
    await upsert_points(settings.QDRANT_COLLECTION_KB, points)
    return len(points)


async def sync_hm_trends(*, max_trends: int = 10, replace_seed: bool = True) -> dict[str, int]:
    """Build seasonal style trends (vector-weighted). H&M products are fetched on user click."""
    season = infer_season(location="Vietnam")
    added = updated = 0
    synced: list[FashionTrend] = []
    kb_indexed = 0

    async with AsyncSessionLocal() as db:
        async with sync_run_context(db, SyncJobType.HM_TRENDS, region=settings.HM_REGION) as run:
            service = TrendService(db)
            signals = await service.aggregate_style_signals(season)

            ranked_specs = sorted(
                STYLE_CATALOG,
                key=lambda s: _score_style(s, signals, season),
                reverse=True,
            )[:max_trends]

            if replace_seed:
                await db.execute(delete(FashionTrend))

            now = datetime.now(timezone.utc)
            for spec in ranked_specs:
                popularity = _score_style(spec, signals, season)
                section = (spec.get("sections") or ["ladies"])[0]
                hm_categories = await _resolve_hm_categories(section)
                source_key = f"style:{spec['title'].lower()}"

                existing = await db.execute(
                    select(FashionTrend).where(FashionTrend.source_url == source_key)
                )
                row = existing.scalar_one_or_none()

                payload = {
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "content": spec["summary"],
                    "image_url": spec["image_url"],
                    "source": "Style Intelligence",
                    "source_url": source_key,
                    "season": season if season in (spec.get("seasons") or []) else (spec.get("seasons") or [season])[0],
                    "tags": spec.get("tags") or [],
                    "popularity": popularity,
                    "published_at": now,
                    "extra": {
                        "style_type": spec.get("style_type"),
                        "hm_category_ids": hm_categories,
                        "section": section,
                        "signal_score": popularity,
                        "vector_signals": {k: signals[k] for k in (spec.get("tags") or [])[:4] if k in signals},
                    },
                }

                if row:
                    for k, v in payload.items():
                        setattr(row, k, v)
                    updated += 1
                    synced.append(row)
                else:
                    trend = FashionTrend(**payload)
                    db.add(trend)
                    added += 1
                    synced.append(trend)

            await db.commit()
            kb_indexed = await _index_trends_to_kb(synced)
            await finalize_sync_run(
                db,
                run,
                items_added=added,
                items_updated=updated,
                items_failed=0,
                meta={"kb_indexed": kb_indexed, "season": season, "style_trends": len(synced)},
            )
            await AnalyticsService(db).log_event(
                None,
                "style_trends_sync",
                {"added": added, "updated": updated, "season": season},
            )

    logger.info(f"Style trends sync: +{added} ~{updated} season={season}")
    return {"added": added, "updated": updated, "kb_indexed": kb_indexed}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=10, dest="max_trends")
    args = parser.parse_args()
    configure_logging()
    await sync_hm_trends(max_trends=args.max_trends)


if __name__ == "__main__":
    asyncio.run(main())
