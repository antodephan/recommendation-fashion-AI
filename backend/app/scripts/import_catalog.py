"""Import fashion catalog from legacy styles.csv + images into Postgres + Qdrant.

Usage:
    python -m app.scripts.import_catalog
    python -m app.scripts.import_catalog --limit 5000 --force
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from sqlalchemy import delete, func, select

from app.config import settings
from app.core.logger import configure_logging, logger
from app.database import AsyncSessionLocal
from app.models.outfit import Outfit, OutfitItem

from ai_engine.catalog_index import index_outfits_to_qdrant

_GENDER_MAP = {
    "men": "male",
    "women": "female",
    "unisex": "unisex",
    "boys": "male",
    "girls": "female",
}


def _normalize_gender(raw: str) -> str:
    return _GENDER_MAP.get((raw or "").strip().lower(), "unisex")


def _row_to_outfit(row: dict, images_dir: Path) -> Outfit | None:
    catalog_id = str(row.get("id", "")).strip()
    if not catalog_id:
        return None

    image_name = f"{catalog_id}.jpg"
    if not (images_dir / image_name).is_file():
        for ext in (".jpeg", ".png", ".webp"):
            alt = f"{catalog_id}{ext}"
            if (images_dir / alt).is_file():
                image_name = alt
                break
        else:
            return None

    name = (row.get("productDisplayName") or row.get("articleType") or "Fashion item").strip()
    color = (row.get("baseColour") or "").strip()
    usage = (row.get("usage") or "casual").strip().lower()
    season = (row.get("season") or "all").strip().lower()
    article = (row.get("articleType") or "apparel").strip()
    sub = (row.get("subCategory") or "").strip()
    master = (row.get("masterCategory") or "").strip()

    tags = [t for t in [master, sub, article, usage, "catalog-import"] if t]
    colors = [color] if color else []

    outfit = Outfit(
        name=name[:255],
        description=f"{article} — {color}".strip(" —")[:2000] if color or article else None,
        image_url=f"/static/catalog/{image_name}",
        style=usage,
        season=season,
        gender=_normalize_gender(row.get("gender", "")),
        occasion=usage,
        colors=colors,
        materials=[],
        tags=tags[:12],
        brand=None,
        price=None,
        rating=4.0,
        popularity=int(row.get("year") or 0) or 100,
        meta={
            "catalog_id": catalog_id,
            "masterCategory": master,
            "subCategory": sub,
            "articleType": article,
            "baseColour": color,
            "usage": usage,
            "year": row.get("year"),
            "source": "styles.csv",
        },
    )
    outfit.items = [
        OutfitItem(
            category=(sub or master or "apparel")[:64],
            name=article[:255] or name[:255],
            color=color or None,
        )
    ]
    return outfit


async def import_catalog(*, limit: int, force: bool, batch_size: int = 200) -> int:
    csv_path = Path(settings.FASHION_CSV_PATH)
    images_dir = Path(settings.FASHION_IMAGES_DIR)

    if not csv_path.is_file():
        logger.warning(f"Catalog CSV not found: {csv_path}")
        return 0
    if not images_dir.is_dir():
        logger.warning(f"Catalog images dir not found: {images_dir}")
        return 0

    async with AsyncSessionLocal() as db:
        tag_filter = Outfit.tags.contains(["catalog-import"])
        existing_q = await db.execute(select(func.count()).select_from(Outfit).where(tag_filter))
        existing = int(existing_q.scalar() or 0)
        if existing > 0 and not force:
            logger.info(f"Catalog already imported ({existing} items); use --force to re-import.")
            return existing

        if force and existing > 0:
            await db.execute(delete(Outfit).where(tag_filter))
            await db.commit()
            logger.info("Cleared previous CSV catalog rows.")

        logger.info(f"Importing up to {limit} rows from {csv_path} …")
        imported: list[Outfit] = []

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if len(imported) >= limit:
                    break
                outfit = _row_to_outfit(row, images_dir)
                if outfit is None:
                    continue
                db.add(outfit)
                imported.append(outfit)
                if len(imported) % batch_size == 0:
                    await db.commit()
                    for o in imported[-batch_size:]:
                        await db.refresh(o)
                    logger.info(f"Committed {len(imported)} catalog rows…")

        if not imported:
            logger.warning("No catalog rows imported (check CSV + image paths).")
            return 0

        await db.commit()
        for o in imported:
            await db.refresh(o)

        logger.info(f"Imported {len(imported)} catalog items; indexing Qdrant…")
        await index_outfits_to_qdrant(imported)
        logger.info("Catalog import complete ✅")
        return len(imported)


async def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Import legacy fashion CSV catalog")
    parser.add_argument("--limit", type=int, default=settings.CATALOG_IMPORT_LIMIT)
    parser.add_argument("--force", action="store_true", help="Replace existing CSV catalog")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    await import_catalog(limit=args.limit, force=args.force, batch_size=args.batch_size)


if __name__ == "__main__":
    asyncio.run(main())
