"""Style trend discovery (vector DB + catalog signals) and lazy H&M outfit fetch."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundError
from app.core.logger import logger
from app.models.outfit import Outfit
from app.models.trend import FashionTrend
from app.services.hm_client import (
    HMClient,
    HMClientError,
    product_colors,
    product_gender,
    product_id,
    product_image,
    product_name,
    product_price,
    product_tags,
    product_url,
)
from app.services.season_service import infer_season

from ai_engine.embeddings import embed_text
from ai_engine.vector_store import search


def current_season(*, location: str | None = "Vietnam") -> str:
    return infer_season(location=location)


class TrendService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_style_trends(
        self,
        *,
        season: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Return editorial style trends for the season (no H&M product cards)."""
        season = (season or current_season()).lower()
        stmt = (
            select(FashionTrend)
            .where(FashionTrend.source != "H&M")
            .where(or_(FashionTrend.season == season, FashionTrend.season == "all"))
            .order_by(FashionTrend.popularity.desc(), FashionTrend.published_at.desc().nullslast())
            .limit(limit)
        )
        rows = await self.db.execute(stmt)
        items = list(rows.scalars().all())
        if not items:
            stmt = (
                select(FashionTrend)
                .where(FashionTrend.source != "H&M")
                .order_by(FashionTrend.popularity.desc(), FashionTrend.created_at.desc())
                .limit(limit)
            )
            rows = await self.db.execute(stmt)
            items = list(rows.scalars().all())
        return [self._serialize_trend(t) for t in items]

    async def get_trend_outfits(self, trend_id: UUID, *, limit: int = 8) -> dict[str, Any]:
        """Fetch H&M product picks for a style trend (called after user clicks)."""
        trend = await self.db.get(FashionTrend, trend_id)
        if not trend:
            raise NotFoundError("Trend not found")

        extra = trend.extra or {}
        client = HMClient()
        region = await client.resolve_region(settings.HM_REGION)
        category_ids: list[str] = list(extra.get("hm_category_ids") or [])
        if not category_ids:
            category_ids = await self._default_categories(client, region, extra.get("section", "ladies"))

        products: list[dict[str, Any]] = []
        seen: set[str] = set()
        trend_tags = {t.lower() for t in (trend.tags or [])}

        for cat_id in category_ids[:4]:
            if len(products) >= limit * 2:
                break
            try:
                batch = await client.list_products(region, category_id=cat_id, page=1, limit=24)
            except HMClientError as exc:
                logger.warning(f"H&M list failed for {cat_id}: {exc}")
                continue
            for p in batch:
                pid = product_id(p)
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                p["_hm_category_id"] = cat_id
                if trend_tags and not self._product_matches_trend(p, trend_tags):
                    continue
                products.append(p)
                if len(products) >= limit:
                    break
            if len(products) >= limit:
                break

        if len(products) < limit:
            for cat_id in category_ids[:2]:
                try:
                    batch = await client.list_products(region, category_id=cat_id, page=1, limit=limit)
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
                if len(products) >= limit:
                    break

        items = [self._hm_product_to_item(p, region, trend) for p in products[:limit]]
        return {
            "trend_id": str(trend.id),
            "title": trend.title,
            "season": trend.season,
            "reasoning": (
                f"Curated H&M pieces aligned with “{trend.title}” — "
                f"a {trend.season or 'seasonal'} style many shoppers are exploring right now."
            ),
            "items": items,
        }

    async def aggregate_style_signals(self, season: str) -> dict[str, float]:
        """Blend Postgres outfit stats with Qdrant retrieval for popularity weights."""
        weights: Counter[str] = Counter()

        tag_rows = await self.db.execute(
            select(Outfit.tags, Outfit.popularity).where(
                or_(Outfit.season == season, Outfit.season == "all", Outfit.season.is_(None))
            )
        )
        for tags, pop in tag_rows.all():
            if not tags:
                continue
            w = max(0.1, float(pop or 0) / 1000.0)
            for tag in tags:
                key = str(tag).lower().strip()
                if key and key not in ("hm", "hm-api"):
                    weights[key] += w

        style_rows = await self.db.execute(
            select(Outfit.style, func.count(), func.avg(Outfit.popularity)).where(
                Outfit.style.isnot(None),
                or_(Outfit.season == season, Outfit.season == "all"),
            ).group_by(Outfit.style)
        )
        for style, count, avg_pop in style_rows.all():
            if style:
                weights[str(style).lower()] += float(count or 0) * 0.05 + float(avg_pop or 0) / 2000.0

        try:
            query = f" trending fashion style {season} popular wardrobe many people wearing"
            vector = await embed_text(query)
            for collection in (settings.QDRANT_COLLECTION_OUTFITS, settings.QDRANT_COLLECTION_KB):
                hits = await search(collection, vector, top_k=12)
                for hit in hits:
                    payload = hit.payload or {}
                    for tag in payload.get("tags") or []:
                        weights[str(tag).lower()] += hit.score * 0.4
                    style = payload.get("style")
                    if style:
                        weights[str(style).lower()] += hit.score * 0.5
        except Exception as exc:
            logger.warning(f"Vector trend signals skipped: {exc}")

        return dict(weights)

    @staticmethod
    def _serialize_trend(t: FashionTrend) -> dict[str, Any]:
        return {
            "id": str(t.id),
            "title": t.title,
            "summary": t.summary,
            "image_url": t.image_url,
            "source": t.source,
            "tags": t.tags or [],
            "season": t.season,
            "popularity": t.popularity,
            "style_type": (t.extra or {}).get("style_type", "style"),
            "published_at": t.published_at.isoformat() if t.published_at else None,
        }

    @staticmethod
    async def _default_categories(client: HMClient, region: str, section: str) -> list[str]:
        cats = await client.list_categories(region)
        section = (section or "ladies").lower()
        ids = [c["category_id"] for c in cats if section in c.get("category_id", "").lower()]
        return ids[:3] or [c["category_id"] for c in cats[:2]]

    @staticmethod
    def _product_matches_trend(product: dict[str, Any], trend_tags: set[str]) -> bool:
        blob = " ".join(
            [
                product_name(product).lower(),
                " ".join(product_tags(product)),
                " ".join(product_colors(product)),
            ]
        )
        return any(tag in blob for tag in trend_tags if len(tag) > 2)

    @staticmethod
    def _hm_product_to_item(product: dict[str, Any], region: str, trend: FashionTrend) -> dict[str, Any]:
        pid = product_id(product)
        price, currency = product_price(product)
        return {
            "outfit_id": pid or product_name(product),
            "name": product_name(product),
            "image_url": product_image(product),
            "score": round(min(0.98, 0.55 + (trend.popularity or 0) * 0.3), 2),
            "why": f"Matches the {trend.title} trend — {trend.season or 'in season'} style pick from H&M.",
            "tags": product_tags(product),
            "price": price,
            "currency": currency,
            "source_url": product_url(product, region),
            "gender": product_gender(product),
        }
