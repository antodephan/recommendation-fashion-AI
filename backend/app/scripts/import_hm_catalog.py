"""Import H&M catalog from RapidAPI into Postgres + Qdrant."""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.core.logger import configure_logging, logger
from app.database import AsyncSessionLocal
from app.models.outfit import Outfit
from app.models.sync_run import SyncJobType
from app.services.analytics_service import AnalyticsService
from app.services.hm_client import (
    HMClient,
    category_section,
    infer_season_from_product,
    product_colors,
    product_gender,
    product_id,
    product_image,
    product_name,
    product_price,
    product_tags,
    product_url,
)
from app.services.sync_run_service import finalize_sync_run, sync_run_context

from ai_engine.catalog_index import index_outfits_to_qdrant


def _parse_sections(raw: str | None = None) -> list[str]:
    text = (raw or settings.HM_CATALOG_SECTIONS).strip()
    return [part.strip().lower() for part in text.split(",") if part.strip()]


def _product_to_outfit(product: dict, region: str) -> Outfit | None:
    pid = product_id(product)
    if not pid:
        return None
    name = product_name(product)
    image = product_image(product)
    price, currency = product_price(product)
    url = product_url(product, region)
    desc = str(product.get("description") or product.get("detail") or "")[:2000] or None
    cat_id = str(product.get("_hm_category_id") or "")
    style = str(
        product.get("sectionName") or product.get("category") or cat_id or "casual"
    )[:64].lower()

    return Outfit(
        name=name,
        description=desc,
        image_url=image,
        style=style,
        season=infer_season_from_product(product),
        gender=product_gender(product),
        occasion=style,
        colors=product_colors(product),
        materials=[],
        tags=product_tags(product),
        brand="H&M",
        price=price,
        currency=currency,
        rating=4.0,
        popularity=100,
        source_url=url,
        is_active=True,
        meta={
            "hm_product_id": pid,
            "hm_category_id": cat_id or None,
            "hm_section": category_section(cat_id) if cat_id else None,
            "region": region,
            "source": "hm-api",
            "raw_category": product.get("category") or product.get("sectionName"),
        },
    )


async def import_hm_catalog(
    *,
    limit: int | None = None,
    force: bool = False,
    sections: list[str] | None = None,
) -> dict[str, int]:
    limit = limit if limit is not None else settings.HM_CATALOG_IMPORT_LIMIT
    target_sections = sections or _parse_sections()
    client = HMClient()
    region = await client.resolve_region(settings.HM_REGION)
    added = updated = failed = 0
    to_index: list[Outfit] = []

    async with AsyncSessionLocal() as db:
        async with sync_run_context(db, SyncJobType.HM_CATALOG, region=region) as run:
            categories = await client.list_categories(region)
            by_section: dict[str, list[dict]] = defaultdict(list)
            for cat in categories:
                cat_id = str(cat.get("category_id") or cat.get("id") or "").strip()
                if not cat_id:
                    continue
                section = category_section(cat_id)
                if section in target_sections:
                    by_section[section].append(cat)

            if not by_section:
                fallbacks = {
                    "ladies": [{"category_id": "ladies_newarrivals_all", "name": "View All"}],
                    "men": [{"category_id": "men_newarrivals_all", "name": "View All"}],
                }
                for section in target_sections:
                    if section in fallbacks:
                        by_section[section] = fallbacks[section]

            active_sections = [s for s in target_sections if by_section.get(s)]
            if not active_sections:
                active_sections = list(by_section.keys())
            per_section = max(1, limit // max(1, len(active_sections)))

            seen_ids: set[str] = set()
            section_counts: dict[str, int] = {s: 0 for s in active_sections}

            async def _upsert(raw: dict, cat_id: str) -> bool:
                nonlocal added, updated, failed
                pid = product_id(raw)
                if not pid or pid in seen_ids:
                    return False
                seen_ids.add(pid)
                raw["_hm_category_id"] = cat_id
                outfit = _product_to_outfit(raw, region)
                if not outfit:
                    failed += 1
                    return False
                try:
                    existing = await db.execute(
                        select(Outfit).where(Outfit.meta.op("->>")("hm_product_id") == pid)
                    )
                    row = existing.scalar_one_or_none()
                    if row:
                        if force:
                            row.name = outfit.name
                            row.description = outfit.description
                            row.image_url = outfit.image_url
                            row.style = outfit.style
                            row.season = outfit.season
                            row.gender = outfit.gender
                            row.price = outfit.price
                            row.currency = outfit.currency
                            row.source_url = outfit.source_url
                            row.tags = outfit.tags
                            row.colors = outfit.colors
                            row.meta = outfit.meta
                            row.updated_at = datetime.now(timezone.utc)
                            to_index.append(row)
                            updated += 1
                            return True
                        return False
                    db.add(outfit)
                    await db.flush()
                    to_index.append(outfit)
                    added += 1
                    return True
                except Exception as exc:
                    logger.warning(f"H&M upsert failed pid={pid}: {exc}")
                    failed += 1
                    return False

            for section in active_sections:
                for cat in by_section.get(section, []):
                    if section_counts[section] >= per_section or len(seen_ids) >= limit:
                        break
                    cat_id = str(cat.get("category_id") or cat.get("id") or "").strip()
                    page = 1
                    while section_counts[section] < per_section and len(seen_ids) < limit:
                        try:
                            products = await client.list_products(
                                region, category_id=cat_id, page=page, sort="NEWEST_FIRST"
                            )
                        except Exception as exc:
                            logger.warning(
                                f"H&M products fetch failed section={section} cat={cat_id} page={page}: {exc}"
                            )
                            break
                        if not products:
                            break
                        for raw in products:
                            if section_counts[section] >= per_section or len(seen_ids) >= limit:
                                break
                            if await _upsert(raw, cat_id):
                                section_counts[section] += 1
                        page += 1
                        if page > 50:
                            break

            await db.commit()
            indexed = await index_outfits_to_qdrant(to_index)
            await finalize_sync_run(
                db,
                run,
                items_added=added,
                items_updated=updated,
                items_failed=failed,
                meta={
                    "indexed": indexed,
                    "region": region,
                    "limit": limit,
                    "sections": active_sections,
                    "per_section": per_section,
                },
            )
            analytics = AnalyticsService(db)
            await analytics.log_event(
                None,
                "hm_catalog_sync",
                {
                    "added": added,
                    "updated": updated,
                    "failed": failed,
                    "region": region,
                    "sections": active_sections,
                },
            )

    logger.info(
        f"H&M catalog import: +{added} ~{updated} !{failed} indexed={len(to_index)} "
        f"region={region} sections={active_sections}"
    )
    return {"added": added, "updated": updated, "failed": failed, "indexed": len(to_index)}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--sections",
        type=str,
        default=None,
        help="Comma-separated sections: ladies, men, kids, beauty, home (default from HM_CATALOG_SECTIONS)",
    )
    args = parser.parse_args()
    configure_logging()
    sections = _parse_sections(args.sections) if args.sections else None
    await import_hm_catalog(limit=args.limit, force=args.force, sections=sections)


if __name__ == "__main__":
    asyncio.run(main())
