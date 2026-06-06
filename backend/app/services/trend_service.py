"""Style trend discovery (vector DB + catalog signals) and lazy H&M outfit fetch."""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import cache_delete_prefix, cache_get, cache_set
from app.core.exceptions import NotFoundError
from app.core.logger import logger
from app.models.outfit import FavoriteOutfit, Outfit
from app.models.trend import FashionTrend
from app.models.user import User
from app.services.hm_client import (
    DEFAULT_HM_CATEGORIES,
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
from app.utils.gender import gender_matches_user, gender_sql_values, normalize_gender
from app.utils.style_matching import (
    expand_style_keywords,
    primary_canonical_style,
    profile_style_tokens,
    resolve_canonical_styles,
    style_category_hints,
    style_match_score,
    tokenize_text,
)
from ai_engine.embeddings import embed_text
from ai_engine.rag import retrieve_context
from ai_engine.vector_store import get_user_profile_vector, search


def current_season(*, location: str | None = "Vietnam") -> str:
    return infer_season(location=location)


async def invalidate_trends_cache() -> None:
    await cache_delete_prefix("trends:")


class TrendService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_style_trend(self, trend_id: UUID) -> dict[str, Any]:
        trend = await self.db.get(FashionTrend, trend_id)
        if not trend:
            raise NotFoundError("Trend not found")
        return self._serialize_trend(trend)

    async def list_style_trends(
        self,
        *,
        season: str | None = None,
        limit: int = 12,
        user: User | None = None,
    ) -> list[dict[str, Any]]:
        """Return editorial style trends for the season (no H&M product cards)."""
        season = (season or current_season()).lower()
        cache_key = f"trends:list:{season}:{limit}"
        cached = await cache_get(cache_key)
        if cached is not None and await self._cached_trends_valid(cached):
            base = cached
        else:
            if cached is not None:
                await cache_delete_prefix("trends:")

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
            base = [self._serialize_trend(t) for t in items]
            await cache_set(cache_key, base, ttl=1800)

        if user:
            return await self._personalize_trends(base, user, season)
        return base

    async def _cached_trends_valid(self, items: list[dict[str, Any]]) -> bool:
        if not items:
            return True
        try:
            trend_id = UUID(str(items[0]["id"]))
        except (KeyError, TypeError, ValueError):
            return False
        return await self.db.get(FashionTrend, trend_id) is not None

    async def get_trend_outfits(
        self,
        trend_id: UUID,
        *,
        limit: int = 8,
        user: User | None = None,
    ) -> dict[str, Any]:
        """Fetch H&M product picks for a style trend (called after user clicks)."""
        section = self._user_hm_section(user) or "ladies"
        cache_key = f"trends:outfits:{trend_id}:{limit}:{section}"
        cached = await cache_get(cache_key)
        if cached is not None:
            payload = cached
        else:
            trend = await self.db.get(FashionTrend, trend_id)
            if not trend:
                raise NotFoundError("Trend not found")

            items: list[dict[str, Any]] = []
            source = "none"
            live_ok = getattr(settings, "HM_LIVE_API_ENABLED", True) and settings.RAPIDAPI_KEY
            if live_ok:
                try:
                    items = await self._hm_outfit_items(trend, limit=limit, user=user)
                    if items:
                        source = "hm_api"
                except Exception as exc:
                    logger.warning(f"H&M trend outfits failed: {exc}")

            if not items:
                items = await self._catalog_outfit_items(trend, limit=limit, user=user)
                if items:
                    source = "hm_catalog"

            payload = {
                "trend_id": str(trend.id),
                "title": trend.title,
                "season": trend.season,
                "source": source,
                "reasoning": (
                    f"Curated H&M pieces aligned with “{trend.title}” — "
                    f"a {trend.season or 'seasonal'} style many shoppers are exploring right now."
                )
                if items
                else (
                    f"No H&M products are available for “{trend.title}” right now. "
                    "Check RapidAPI key, H&M import, or try again later."
                ),
                "items": items,
            }
            if items:
                await cache_set(cache_key, payload, ttl=3600)

        if user and payload.get("items"):
            trend = await self.db.get(FashionTrend, trend_id)
            if trend:
                personalized = await self._personalize_outfit_payload(payload, trend, user)
                if personalized.get("items"):
                    return personalized
                # Cached/fetched items were wrong gender — rebuild for this user
                logger.info(
                    f"Trend outfits empty after personalize for user {user.id}; refetching"
                )
                await cache_delete_prefix(f"trends:outfits:{trend_id}:")
                return await self._fetch_trend_outfits_fresh(
                    trend, limit=limit, user=user, section=section
                )
        return payload

    async def _fetch_trend_outfits_fresh(
        self,
        trend: FashionTrend,
        *,
        limit: int,
        user: User | None,
        section: str,
    ) -> dict[str, Any]:
        """Fetch trend outfits without cache (after gender mismatch)."""
        items: list[dict[str, Any]] = []
        source = "none"
        live_ok = getattr(settings, "HM_LIVE_API_ENABLED", True) and settings.RAPIDAPI_KEY
        if live_ok:
            try:
                items = await self._hm_outfit_items(trend, limit=limit, user=user)
                if items:
                    source = "hm_api"
            except Exception as exc:
                logger.warning(f"H&M trend outfits refetch failed: {exc}")

        if not items:
            items = await self._catalog_outfit_items(trend, limit=limit, user=user)
            if items:
                source = "hm_catalog"

        payload = {
            "trend_id": str(trend.id),
            "title": trend.title,
            "season": trend.season,
            "source": source,
            "reasoning": (
                f"Curated H&M pieces aligned with “{trend.title}” — "
                f"a {trend.season or 'seasonal'} style many shoppers are exploring right now."
            )
            if items
            else (
                f"No H&M products are available for “{trend.title}” right now. "
                "Check RapidAPI key, H&M import, or try again later."
            ),
            "items": items,
        }
        if items:
            cache_key = f"trends:outfits:{trend.id}:{limit}:{section}"
            await cache_set(cache_key, payload, ttl=3600)

        if user and items:
            return await self._personalize_outfit_payload(payload, trend, user)
        return payload

    async def _hm_outfit_items(
        self,
        trend: FashionTrend,
        *,
        limit: int,
        user: User | None = None,
    ) -> list[dict[str, Any]]:
        extra = trend.extra or {}
        client = HMClient()
        region = await client.resolve_region(settings.HM_REGION)
        user_section = self._user_hm_section(user)
        section = user_section or extra.get("section", "ladies")
        category_ids: list[str] = list(extra.get("hm_category_ids") or [])
        if category_ids and user_section:
            category_ids = self._remap_hm_categories(category_ids, user_section)
        if not category_ids:
            category_ids = await self._default_categories(client, region, section)
        if user:
            styles = (user.preferences or {}).get("styles") or []
            if styles:
                category_ids = await self._style_aware_categories(
                    client, region, section, styles, category_ids
                )

        trend_tags = {t.lower() for t in (trend.tags or []) if len(t) > 2}
        trend_style = (extra.get("style_type") or "").lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        seen: set[str] = set()

        async def fetch_category(cat_id: str, page: int = 1) -> tuple[str, list[dict[str, Any]]]:
            try:
                batch = await client.list_products(
                    region, category_id=cat_id, page=page, limit=24
                )
                return cat_id, batch
            except HMClientError as exc:
                logger.warning(f"H&M list failed for {cat_id} p{page}: {exc}")
                return cat_id, []

        category_ids = category_ids[:6]
        fetch_jobs = [
            fetch_category(cat_id, page)
            for cat_id in category_ids
            for page in (1, 2)
        ]
        batch_results = await asyncio.gather(*fetch_jobs)
        user_gender = normalize_gender(user.gender) if user else None

        for cat_id, batch in batch_results:
            for p in batch:
                pid = product_id(p)
                if not pid or pid in seen:
                    continue
                p["_hm_category_id"] = cat_id
                if user_gender and not gender_matches_user(user_gender, product_gender(p)):
                    continue
                seen.add(pid)
                score = self._product_trend_score(
                    p, trend_tags, user=user, trend_style_type=trend_style
                )
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        products = self._diverse_product_pick(scored, limit=limit)

        if not products and category_ids:
            for cat_id in category_ids[:3]:
                for page in (1, 2, 3):
                    cat_id_res, batch = await fetch_category(cat_id, page)
                    for p in batch:
                        pid = product_id(p)
                        if not pid or pid in seen:
                            continue
                        if user_gender and not gender_matches_user(user_gender, product_gender(p)):
                            continue
                        seen.add(pid)
                        p["_hm_category_id"] = cat_id_res
                        products.append(p)
                        if len(products) >= limit:
                            break
                    if len(products) >= limit:
                        break
                if len(products) >= limit:
                    break

        return [self._hm_product_to_item(p, region, trend, user=user) for p in products[:limit]]

    async def _catalog_outfit_items(
        self, trend: FashionTrend, *, limit: int, user: User | None = None
    ) -> list[dict[str, Any]]:
        """Fallback only for H&M rows previously imported into Postgres."""
        extra = trend.extra or {}
        style_type = extra.get("style_type")
        hm_only = or_(
            Outfit.source_url.ilike("%hm.com%"),
            Outfit.image_url.ilike("%hm.com%"),
            Outfit.tags.any("hm-api"),
        )
        stmt = (
            select(Outfit)
            .where(Outfit.is_active.is_(True))
            .where(Outfit.brand == "H&M")
            .where(hm_only)
        )
        gender_values = gender_sql_values(normalize_gender(user.gender) if user else None)
        if gender_values:
            stmt = stmt.where(or_(*[Outfit.gender == g for g in gender_values]))
        if style_type:
            stmt = stmt.where(
                or_(Outfit.style == style_type, Outfit.style.is_(None))
            )
        if trend.season and trend.season != "all":
            stmt = stmt.where(
                or_(Outfit.season == trend.season, Outfit.season == "all", Outfit.season.is_(None))
            )
        stmt = stmt.order_by(Outfit.popularity.desc()).limit(limit)
        rows = await self.db.execute(stmt)
        outfits = list(rows.scalars().all())

        return [
            {
                "outfit_id": str(o.id),
                "name": o.name,
                "image_url": o.image_url,
                "score": round(min(0.95, 0.5 + (trend.popularity or 0) * 0.35), 2),
                "why": f"H&M catalog match for {trend.title} — {trend.season or 'in season'} styling.",
                "tags": o.tags or [],
                "price": o.price,
                "currency": o.currency or "USD",
                "source_url": o.source_url,
                "gender": o.gender,
            }
            for o in outfits
        ]

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

    async def _personalize_trends(
        self,
        items: list[dict[str, Any]],
        user: User,
        season: str,
    ) -> list[dict[str, Any]]:
        """Re-rank trends using profile, favorites, RAG context and profile vector."""
        if not items:
            return items

        profile = self._build_user_profile(user)
        profile_tokens = self._profile_tokens(profile)
        favorite_tokens = await self._favorite_style_tokens(user.id)
        user_gender = normalize_gender(profile.get("gender"))

        styles = profile.get("styles") or []
        query = f"personalized fashion style trends for {season}"
        if styles:
            query += f" matching {', '.join(styles[:4])}"
        if profile.get("colors"):
            query += f" in {', '.join(profile['colors'][:3])}"

        rag_docs, vector_scores = await asyncio.gather(
            retrieve_context(
                query,
                user_id=str(user.id),
                top_k=8,
                user_profile=profile,
            ),
            self._profile_vector_trend_scores(user.id),
        )

        rag_tokens: set[str] = set()
        for doc in rag_docs:
            rag_tokens |= self._tokens(doc.text)
            for tag in doc.metadata.get("tags") or []:
                rag_tokens.add(str(tag).lower())

        ranked: list[dict[str, Any]] = []
        for item in items:
            trend_tokens = self._trend_tokens(item)
            if user_gender == "male" and trend_tokens & {"women", "female", "ladies", "dress", "skirt", "heels"}:
                continue
            if user_gender == "female" and trend_tokens & {"men", "male", "mens", "suit", "tie"} and not trend_tokens & {"women", "female", "unisex"}:
                continue
            profile_overlap = self._overlap(profile_tokens, trend_tokens)
            favorite_overlap = self._overlap(favorite_tokens, trend_tokens)
            rag_overlap = self._overlap(rag_tokens, trend_tokens)
            vector_score = vector_scores.get(str(item["id"]), 0.0)

            personal_score = (
                0.30 * float(item.get("popularity") or 0)
                + 0.25 * profile_overlap
                + 0.15 * favorite_overlap
                + 0.10 * rag_overlap
                + 0.20 * vector_score
            )
            ranked.append(
                {
                    **item,
                    "personal_score": round(min(1.0, personal_score), 3),
                    "match_reason": self._match_reason_for_trend(
                        profile,
                        item,
                        profile_overlap,
                        favorite_overlap,
                    ),
                }
            )

        ranked.sort(
            key=lambda x: (x.get("personal_score", 0), x.get("popularity", 0)),
            reverse=True,
        )
        return ranked

    async def _personalize_outfit_payload(
        self,
        payload: dict[str, Any],
        trend: FashionTrend,
        user: User,
    ) -> dict[str, Any]:
        profile = self._build_user_profile(user)
        profile_tokens = self._profile_tokens(profile)
        trend_tags = {t.lower() for t in (trend.tags or []) if len(t) > 2}

        query = (
            f"H&M outfit picks for {trend.title} trend matching my style preferences"
        )
        rag_docs = await retrieve_context(
            query,
            user_id=str(user.id),
            top_k=4,
            user_profile=profile,
            enable_query_rewrite=False,
        )
        rag_hint = rag_docs[0].text[:160] if rag_docs else ""

        rescored: list[tuple[float, dict[str, Any]]] = []
        user_gender = normalize_gender(profile.get("gender"))
        for item in payload.get("items") or []:
            if user_gender and not gender_matches_user(user_gender, item.get("gender")):
                continue
            item_blob = " ".join(
                [
                    str(item.get("name") or ""),
                    " ".join(str(t) for t in item.get("tags") or []),
                ]
            )
            style_score = style_match_score(
                profile.get("styles"),
                item_blob,
                trend_tags=trend_tags,
                trend_style_type=(trend.extra or {}).get("style_type"),
            )
            item_tokens = tokenize_text(item_blob)
            profile_tokens_expanded = profile_style_tokens(profile)
            profile_overlap = (
                len(profile_tokens_expanded & item_tokens) / len(profile_tokens_expanded)
                if profile_tokens_expanded and item_tokens
                else 0.0
            )
            trend_overlap = self._overlap(trend_tags, item_tokens)
            budget_penalty = self._budget_penalty(profile, item)
            gender_boost = self._gender_boost(profile, item)

            score = (
                float(item.get("score") or 0.5) * 0.25
                + style_score * 0.40
                + profile_overlap * 0.15
                + trend_overlap * 0.15
                + gender_boost * 0.10
                - budget_penalty * 0.15
            )
            why = self._match_reason_for_item(
                profile, item, max(style_score, profile_overlap), trend.title, style_score
            )
            rescored.append(
                (
                    score,
                    {
                        **item,
                        "score": round(min(0.99, max(0.1, score)), 2),
                        "why": why,
                    },
                )
            )

        rescored.sort(key=lambda x: x[0], reverse=True)
        items = [entry for _, entry in rescored]

        reasoning = payload.get("reasoning") or ""
        if profile.get("styles"):
            tail = reasoning or "aligned with this trend."
            reasoning = (
                f"Picks ranked for your {', '.join(profile['styles'][:2])} style — {tail}"
            )
        elif rag_hint:
            reasoning = f"Personalized from your style history — {rag_hint}"

        return {**payload, "items": items, "reasoning": reasoning}

    async def _profile_vector_trend_scores(self, user_id: UUID) -> dict[str, float]:
        vector = await get_user_profile_vector(str(user_id))
        if not vector:
            return {}
        hits = await search(settings.QDRANT_COLLECTION_KB, vector, top_k=24)
        return {str(h.id): float(h.score) for h in hits}

    async def _favorite_style_tokens(self, user_id: UUID) -> set[str]:
        stmt = (
            select(Outfit.style, Outfit.tags, Outfit.colors)
            .join(FavoriteOutfit, FavoriteOutfit.outfit_id == Outfit.id)
            .where(FavoriteOutfit.user_id == user_id)
            .limit(40)
        )
        rows = await self.db.execute(stmt)
        tokens: set[str] = set()
        for style, tags, colors in rows.all():
            if style:
                tokens.add(str(style).lower())
            for tag in tags or []:
                if len(str(tag)) > 2:
                    tokens.add(str(tag).lower())
            for color in colors or []:
                tokens.add(str(color).lower())
        return tokens

    @staticmethod
    def _build_user_profile(user: User) -> dict[str, Any]:
        prefs = user.preferences or {}
        return {
            "gender": user.gender,
            "body_type": user.body_type,
            "location": user.location,
            "budget": prefs.get("budget"),
            "colors": prefs.get("colors", []),
            "brands": prefs.get("brands", []),
            "styles": prefs.get("styles", []),
            "avoid": prefs.get("avoid", []),
        }

    @staticmethod
    def _profile_tokens(profile: dict[str, Any]) -> set[str]:
        tokens = profile_style_tokens(profile)
        for key in ("gender", "body_type", "location"):
            if profile.get(key):
                tokens |= tokenize_text(str(profile[key]))
        return tokens

    @staticmethod
    def _trend_tokens(item: dict[str, Any]) -> set[str]:
        parts = [
            str(item.get("title") or ""),
            str(item.get("summary") or ""),
            str(item.get("style_type") or ""),
            " ".join(str(t) for t in item.get("tags") or []),
        ]
        return TrendService._tokens(" ".join(parts))

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return tokenize_text(text)

    @staticmethod
    async def _style_aware_categories(
        client: HMClient,
        region: str,
        section: str,
        styles: list[str],
        base_ids: list[str],
    ) -> list[str]:
        """Prioritize H&M categories that fit the user's style preferences."""
        hints = style_category_hints(styles, section)
        try:
            cats = await client.list_categories(region)
            prefix = "men" if section == "men" else "ladies"
            prioritized = [
                c["category_id"]
                for c in cats
                if c.get("category_id", "").lower().startswith(prefix)
                and any(h in c["category_id"].lower() for h in hints)
            ]
            return list(dict.fromkeys([*prioritized[:5], *base_ids]))[:8]
        except HMClientError:
            return base_ids

    @staticmethod
    def _overlap(needles: set[str], haystack: set[str]) -> float:
        if not needles or not haystack:
            return 0.0
        return len(needles & haystack) / len(needles)

    @staticmethod
    def _remap_hm_categories(category_ids: list[str], section: str) -> list[str]:
        """Map trend category IDs (often ladies) to the user's H&M section."""
        section = (section or "ladies").lower()
        remapped: list[str] = []
        for cid in category_ids:
            low = cid.lower()
            if section == "men":
                if low.startswith("men"):
                    remapped.append(cid)
                elif "ladies" in low or "women" in low:
                    remapped.append(
                        low.replace("ladies", "men").replace("women", "men")
                    )
                elif "sportswear" in low:
                    remapped.append(low.replace("ladies", "men"))
            elif section == "ladies":
                if low.startswith("ladies") or "women" in low:
                    remapped.append(cid)
                elif low.startswith("men"):
                    remapped.append(
                        low.replace("men", "ladies").replace("women", "ladies")
                    )
            else:
                remapped.append(cid)
        # Drop IDs that still belong to the wrong section
        if section == "men":
            remapped = [c for c in remapped if c.lower().startswith("men") or "men_" in c.lower()]
        elif section == "ladies":
            remapped = [
                c for c in remapped
                if c.lower().startswith("ladies") or "ladies" in c.lower()
            ]
        return list(dict.fromkeys(remapped))

    @staticmethod
    def _user_hm_section(user: User | None) -> str | None:
        if not user or not user.gender:
            return None
        gender = normalize_gender(user.gender)
        if gender == "male":
            return "men"
        if gender == "female":
            return "ladies"
        return None

    @staticmethod
    def _diverse_product_pick(
        scored: list[tuple[float, dict[str, Any]]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Select top products while spreading across garment types."""
        ordered = sorted(scored, key=lambda x: x[0], reverse=True)
        picked: list[dict[str, Any]] = []
        seen_types: set[str] = set()
        seen_ids: set[str] = set()
        top_score = ordered[0][0] if ordered else 0.0

        def _garment_key(product: dict[str, Any]) -> str:
            name = product_name(product).lower()
            for token in (
                "dress", "shirt", "pant", "trouser", "jean", "jacket", "coat",
                "skirt", "hoodie", "sweater", "top", "short", "jogger", "track",
            ):
                if token in name:
                    return token
            tags = product_tags(product)
            return tags[0] if tags else name[:24]

        for score, product in ordered:
            if len(picked) >= limit:
                break
            pid = product_id(product) or product_name(product)
            if pid in seen_ids:
                continue
            key = _garment_key(product)
            if (
                key in seen_types
                and len(picked) >= max(3, limit // 2)
                and score < top_score * 0.82
            ):
                continue
            seen_types.add(key)
            seen_ids.add(pid)
            picked.append(product)

        if len(picked) < limit:
            for _, product in ordered:
                if len(picked) >= limit:
                    break
                pid = product_id(product) or product_name(product)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    picked.append(product)
        return picked[:limit]

    @staticmethod
    def _budget_penalty(profile: dict[str, Any], item: dict[str, Any]) -> float:
        budget = profile.get("budget")
        price = item.get("price")
        if budget is None or price is None:
            return 0.0
        try:
            budget_f = float(budget)
            price_f = float(price)
        except (TypeError, ValueError):
            return 0.0
        if price_f <= budget_f:
            return 0.0
        return min(1.0, (price_f - budget_f) / max(budget_f, 1.0))

    @staticmethod
    def _gender_boost(profile: dict[str, Any], item: dict[str, Any]) -> float:
        user_gender = normalize_gender(profile.get("gender"))
        item_gender = normalize_gender(item.get("gender"))
        if not user_gender:
            return 0.0
        if gender_matches_user(user_gender, item_gender):
            return 1.0 if item_gender == user_gender else 0.6
        return -1.0

    @staticmethod
    def _match_reason_for_trend(
        profile: dict[str, Any],
        item: dict[str, Any],
        profile_overlap: float,
        favorite_overlap: float,
    ) -> str:
        styles = profile.get("styles") or []
        overlap_tags = set(styles) & set(item.get("tags") or [])
        if overlap_tags:
            return f"Matches your {next(iter(overlap_tags))} style preference"
        if profile_overlap >= 0.2:
            return "Aligned with your saved style profile"
        if favorite_overlap >= 0.15:
            return "Similar to outfits you've saved"
        if styles:
            return f"Trending pick for {styles[0]} lovers this season"
        return "Recommended for you this season"

    @staticmethod
    def _match_reason_for_item(
        profile: dict[str, Any],
        item: dict[str, Any],
        profile_overlap: float,
        trend_title: str,
        style_score: float = 0.0,
    ) -> str:
        colors = profile.get("colors") or []
        styles = profile.get("styles") or []
        item_blob = " ".join(
            [str(item.get("name") or ""), " ".join(str(t) for t in item.get("tags") or [])]
        ).lower()
        matched_colors = [c for c in colors if str(c).lower() in item_blob]
        if style_score >= 0.35 and styles:
            return f"Matches your {styles[0]} style — great for {trend_title}."
        if matched_colors:
            return (
                f"Fits the {trend_title} trend and your preferred "
                f"{matched_colors[0]} tones."
            )
        if profile_overlap >= 0.2 and styles:
            return f"{trend_title} pick tailored to your {styles[0]} style."
        return str(item.get("why") or f"Strong match for the {trend_title} trend.")

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
        section = (section or "ladies").lower()
        static = DEFAULT_HM_CATEGORIES.get(section) or DEFAULT_HM_CATEGORIES["ladies"]
        try:
            cats = await client.list_categories(region)
            prefix = "men" if section == "men" else "ladies"
            ids = [
                c["category_id"]
                for c in cats
                if c.get("category_id", "").lower().startswith(prefix)
            ]
            preferred = [
                cid for cid in ids
                if any(k in cid.lower() for k in ("newarrivals", "viewall", "dress", "shirt", "trouser", "jacket", "top"))
            ]
            merged = list(dict.fromkeys([*preferred[:6], *static]))
            return merged[:6] or static
        except HMClientError:
            return static

    @staticmethod
    def _hm_product_to_item(
        product: dict[str, Any],
        region: str,
        trend: FashionTrend,
        *,
        user: User | None = None,
    ) -> dict[str, Any]:
        pid = product_id(product)
        price, currency = product_price(product)
        why = f"Matches the {trend.title} trend — {trend.season or 'in season'} style pick from H&M."
        if user:
            profile = TrendService._build_user_profile(user)
            styles = profile.get("styles") or []
            blob = " ".join([product_name(product).lower(), " ".join(product_tags(product))])
            style_score = style_match_score(styles, blob, trend_style_type=(trend.extra or {}).get("style_type"))
            colors = profile.get("colors") or []
            matched = [c for c in colors if str(c).lower() in blob]
            if style_score >= 0.3 and styles:
                why = f"Matches your {styles[0]} style for {trend.title}."
            elif matched:
                why = f"{trend.title} pick in your preferred {matched[0]} tones."
            elif styles:
                why = f"{trend.title} piece aligned with your {styles[0]} style."
        return {
            "outfit_id": pid or product_name(product),
            "name": product_name(product),
            "image_url": product_image(product),
            "score": round(min(0.98, 0.55 + (trend.popularity or 0) * 0.3), 2),
            "why": why,
            "tags": product_tags(product),
            "price": price,
            "currency": currency,
            "source_url": product_url(product, region),
            "gender": product_gender(product),
        }

    @staticmethod
    def _product_trend_score(
        product: dict[str, Any],
        trend_tags: set[str],
        *,
        user: User | None = None,
        trend_style_type: str | None = None,
    ) -> float:
        blob = " ".join(
            [
                product_name(product).lower(),
                " ".join(product_tags(product)),
                " ".join(product_colors(product)),
            ]
        )
        trend_score = 0.5
        if trend_tags:
            hits = sum(1 for tag in trend_tags if tag in blob)
            trend_score = hits / max(len(trend_tags), 1)

        if trend_style_type:
            style_kw = expand_style_keywords([trend_style_type])
            if any(k in blob for k in style_kw):
                trend_score = max(trend_score, 0.75)

        if not user:
            return trend_score

        profile = TrendService._build_user_profile(user)
        user_gender = normalize_gender(profile.get("gender"))
        if user_gender and not gender_matches_user(user_gender, product_gender(product)):
            return 0.0

        style_score = style_match_score(
            profile.get("styles"),
            blob,
            trend_tags=trend_tags,
            trend_style_type=trend_style_type,
        )
        canon = primary_canonical_style(profile.get("styles"))
        if trend_style_type in {"athleisure", "sporty"} or canon == "athleisure":
            off_style = ("chino", "linen", "formal", "suit", "bikini", "scarf", "pillow", "dress")
            if any(x in blob for x in off_style):
                style_score *= 0.35
        avoid_blob = " ".join(str(a) for a in profile.get("avoid") or [])
        avoid_penalty = 0.0
        if avoid_blob:
            avoid_kw = expand_style_keywords([avoid_blob]) | tokenize_text(avoid_blob)
            avoid_penalty = sum(0.15 for kw in avoid_kw if kw in blob)

        return max(
            0.0,
            trend_score * 0.30 + style_score * 0.55 - avoid_penalty,
        )
