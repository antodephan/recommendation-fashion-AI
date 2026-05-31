"""Sync fashion trends from H&M new arrivals (product-driven)."""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.core.logger import configure_logging, logger
from app.database import AsyncSessionLocal
from app.models.sync_run import SyncJobType
from app.models.trend import FashionTrend
from app.services.analytics_service import AnalyticsService
from app.services.hm_client import (
    HMClient,
    HMClientError,
    product_id,
    product_image,
    product_name,
    product_url,
)
from app.services.season_service import infer_season
from app.services.sync_run_service import finalize_sync_run, sync_run_context

from ai_engine.embeddings import embed_texts
from ai_engine.vector_store import ensure_collections, upsert_points


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
            {"title": t.title, "text": text, "source": "hm-trend", "season": t.season},
        )
        for t, vec, text in zip(trends, vectors, texts)
    ]
    await upsert_points(settings.QDRANT_COLLECTION_KB, points)
    return len(points)


def _humanize_category_id(category_id: str) -> str:
    text = category_id.replace("_", " ").strip()
    for prefix in ("ladies ", "men ", "kids ", "home "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.title() or "New Arrivals"


async def _fetch_new_products(
    client: HMClient, region: str, *, limit: int = 60
) -> tuple[list[dict], dict[str, str]]:
    products: list[dict] = []
    seen: set[str] = set()
    categories = await client.list_categories(region)
    cat_name_map = {c["category_id"]: c["name"] for c in categories if c.get("category_id")}
    cat_ids = [c["category_id"] for c in categories[:12]]
    if not cat_ids:
        cat_ids = ["ladies_newarrivals_all", "men_newarrivals_all", "kids_newborn_viewall"]

    for cat_id in cat_ids:
        if len(products) >= limit:
            break
        try:
            batch = await client.list_products(
                region,
                category_id=cat_id,
                page=1,
                limit=min(24, limit - len(products)),
            )
        except HMClientError:
            continue
        for p in batch:
            pid = product_id(p)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            p["_hm_category_id"] = cat_id
            products.append(p)
            if len(products) >= limit:
                break
    return products, cat_name_map


async def sync_hm_trends(*, max_trends: int = 12, replace_seed: bool = True) -> dict[str, int]:
    client = HMClient()
    region = await client.resolve_region(settings.HM_REGION)
    season = infer_season(location="Vietnam")
    added = updated = 0
    new_trends: list[FashionTrend] = []
    kb_indexed = 0
    products: list[dict] = []

    async with AsyncSessionLocal() as db:
        async with sync_run_context(db, SyncJobType.HM_TRENDS, region=region) as run:
            products, cat_name_map = await _fetch_new_products(client, region, limit=max(48, max_trends * 5))
            if not products:
                raise HMClientError(
                    f"No products returned for country '{region}'. Check RapidAPI subscription."
                )

            by_category: dict[str, list[dict]] = defaultdict(list)
            for p in products:
                cat_id = str(p.get("_hm_category_id") or "new_arrivals")
                by_category[cat_id].append(p)

            ranked = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)[:max_trends]
            now = datetime.now(timezone.utc)

            if replace_seed:
                await db.execute(delete(FashionTrend).where(FashionTrend.source != "H&M"))

            for cat_id, cat_products in ranked:
                cat_label = cat_name_map.get(cat_id) or _humanize_category_id(cat_id)
                hero = cat_products[0]
                pid = product_id(hero)
                title = f"{cat_label} — H&M New In"
                source_url = product_url(hero, region) or f"hm://trend/{pid or cat_id}"

                existing = await db.execute(
                    select(FashionTrend).where(FashionTrend.source_url == source_url)
                )
                row = existing.scalar_one_or_none()

                sample_names = ", ".join(product_name(p) for p in cat_products[:3])
                summary = (
                    f"Fresh {cat_label.lower()} picks this {season}: {sample_names}. "
                    f"{len(cat_products)} new styles from H&M ({region.upper()} catalog)."
                )[:500]
                popularity = min(1.0, 0.35 + len(cat_products) / 20.0)

                payload = {
                    "title": title[:255],
                    "summary": summary,
                    "content": summary,
                    "image_url": product_image(hero),
                    "source": "H&M",
                    "source_url": source_url,
                    "season": season,
                    "tags": ["hm", cat_label.lower().replace(" ", "-"), season],
                    "popularity": popularity,
                    "published_at": now,
                    "extra": {
                        "hm_product_id": pid,
                        "category": cat_label,
                        "category_id": cat_id,
                        "product_count": len(cat_products),
                        "region": region,
                    },
                }

                if row:
                    for k, v in payload.items():
                        setattr(row, k, v)
                    updated += 1
                    new_trends.append(row)
                else:
                    trend = FashionTrend(**payload)
                    db.add(trend)
                    added += 1
                    new_trends.append(trend)

            await db.commit()
            kb_indexed = await _index_trends_to_kb(new_trends)
            await finalize_sync_run(
                db,
                run,
                items_added=added,
                items_updated=updated,
                items_failed=0,
                meta={
                    "kb_indexed": kb_indexed,
                    "region": region,
                    "season": season,
                    "products_fetched": len(products),
                },
            )
            await AnalyticsService(db).log_event(
                None,
                "hm_trends_sync",
                {"added": added, "updated": updated, "region": region},
            )

    logger.info(f"H&M trends sync: +{added} ~{updated} products={len(products)} region={region}")
    return {"added": added, "updated": updated, "kb_indexed": kb_indexed}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=12, dest="max_trends")
    args = parser.parse_args()
    configure_logging()
    await sync_hm_trends(max_trends=args.max_trends)


if __name__ == "__main__":
    asyncio.run(main())
