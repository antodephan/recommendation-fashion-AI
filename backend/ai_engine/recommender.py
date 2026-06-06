"""Hybrid fashion recommendation engine.

Combines:
    - Vector similarity (Qdrant)
    - Content-based filtering (SQL, attributes)
    - Trend-based signals (popularity / rating)
    - Collaborative signals (favorites / recent likes)
    - LLM reasoning + re-ranking
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import logger
from app.models.outfit import FavoriteOutfit, Outfit
from app.models.user import User
from app.schemas.outfit import OutfitFilters

from ai_engine.catalog_similarity import describe_image_for_query, find_image_matches
from ai_engine.embeddings import embed_text
from ai_engine.image_bytes import load_image_bytes
from ai_engine.llm import LLMService
from ai_engine.prompts import RECOMMENDATION_PROMPT, SYSTEM_PROMPT, language_instruction, render_candidates, render_profile
from ai_engine.rag import format_kb_block, retrieve_context
from ai_engine.vector_store import VectorHit, get_user_profile_vector, search
from app.services.season_service import season_context_block


@dataclass
class HybridResult:
    reasoning: str
    confidence: float
    trend_score: float
    items: list[dict[str, Any]]    # [{ outfit_id, score, why }]


class RecommendationEngine:
    """Orchestrates retrieval + LLM re-ranking."""

    def __init__(self, db: AsyncSession, llm: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm or LLMService()

    # ----------------------------------------------------------------- #
    # Candidate generation
    # ----------------------------------------------------------------- #
    async def _vector_candidates(
        self, query: str, filters: OutfitFilters, k: int = 30
    ) -> list[VectorHit]:
        embedding = await embed_text(query)
        filter_payload: dict[str, Any] = {}
        if filters.style:
            filter_payload["style"] = filters.style
        if filters.season:
            filter_payload["season"] = filters.season
        if filters.gender:
            filter_payload["gender"] = filters.gender
        return await search(
            settings.QDRANT_COLLECTION_OUTFITS,
            embedding,
            top_k=k,
            filter_payload=filter_payload or None,
        )

    async def _user_profile_candidates(self, user: User, k: int = 15) -> list[VectorHit]:
        vector = await get_user_profile_vector(str(user.id))
        if not vector:
            return []
        return await search(settings.QDRANT_COLLECTION_OUTFITS, vector, top_k=k)

    async def _content_candidates(self, filters: OutfitFilters, k: int = 20) -> list[Outfit]:
        stmt = select(Outfit).where(Outfit.is_active.is_(True))
        if filters.style:
            stmt = stmt.where(Outfit.style == filters.style)
        if filters.season:
            stmt = stmt.where(Outfit.season == filters.season)
        if filters.gender:
            stmt = stmt.where(Outfit.gender == filters.gender)
        if filters.max_price is not None:
            stmt = stmt.where(Outfit.price <= filters.max_price)
        stmt = stmt.order_by(desc(Outfit.popularity), desc(Outfit.rating)).limit(k)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _image_candidates(
        self, image_url: str | None, *, k: int = 25
    ) -> list[VectorHit]:
        """Similar catalog items from inspiration photo (legacy KNN + vision/Qdrant)."""
        if not image_url:
            return []
        try:
            image_bytes = load_image_bytes(image_url)
        except Exception as exc:
            logger.warning(f"Could not load inspiration image: {exc}")
            return []

        matches, meta = await find_image_matches(image_bytes, top_k=k)
        logger.info(f"Image match sources: {meta}")

        hits: list[VectorHit] = []
        catalog_ids = [m.catalog_id for m in matches if m.catalog_id and not m.outfit_id]

        if catalog_ids:
            result = await self.db.execute(
                select(Outfit).where(
                    Outfit.is_active.is_(True),
                    or_(*[Outfit.meta.contains({"catalog_id": cid}) for cid in catalog_ids[:30]]),
                )
            )
            by_catalog = {str((o.meta or {}).get("catalog_id")): o for o in result.scalars().all()}
            for m in matches:
                if m.outfit_id:
                    hits.append(
                        VectorHit(id=m.outfit_id, score=m.score, payload={"source": m.source})
                    )
                elif m.catalog_id and str(m.catalog_id) in by_catalog:
                    o = by_catalog[str(m.catalog_id)]
                    hits.append(
                        VectorHit(
                            id=str(o.id),
                            score=m.score,
                            payload={"catalog_id": m.catalog_id, "source": m.source},
                        )
                    )
        else:
            for m in matches:
                if m.outfit_id:
                    hits.append(
                        VectorHit(id=m.outfit_id, score=m.score, payload={"source": m.source})
                    )

        return hits[:k]

    async def _collaborative_candidates(self, user: User, k: int = 10) -> list[Outfit]:
        """Outfits frequently favorited by users who liked what this user liked."""
        liked_ids_q = (
            select(FavoriteOutfit.outfit_id).where(FavoriteOutfit.user_id == user.id)
        )
        # similar users: those who also favorited any of the user's favorites
        peers_q = (
            select(FavoriteOutfit.user_id)
            .where(FavoriteOutfit.outfit_id.in_(liked_ids_q))
            .where(FavoriteOutfit.user_id != user.id)
        )
        # outfits favorited by peers, ordered by frequency
        stmt = (
            select(Outfit, func.count().label("freq"))
            .join(FavoriteOutfit, FavoriteOutfit.outfit_id == Outfit.id)
            .where(FavoriteOutfit.user_id.in_(peers_q))
            .where(Outfit.id.notin_(liked_ids_q))
            .group_by(Outfit.id)
            .order_by(desc("freq"))
            .limit(k)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    # ----------------------------------------------------------------- #
    # Merging
    # ----------------------------------------------------------------- #
    @staticmethod
    def _merge_candidates(
        vector_hits: list[VectorHit],
        content: list[Outfit],
        collaborative: list[Outfit],
        image_hits: list[VectorHit] | None = None,
        profile_hits: list[VectorHit] | None = None,
        season: str | None = None,
        limit: int = 25,
    ) -> dict[str, dict[str, Any]]:
        """Combine candidates by id with weighted score."""
        merged: dict[str, dict[str, Any]] = {}
        has_image = bool(image_hits)
        has_profile = bool(profile_hits)
        if has_image:
            text_w, image_w, content_w, collab_w, profile_w = 0.3, 0.3, 0.12, 0.13, 0.15
        elif has_profile:
            text_w, image_w, content_w, collab_w, profile_w = 0.45, 0.0, 0.15, 0.15, 0.25
        else:
            text_w, image_w, content_w, collab_w, profile_w = 0.6, 0.0, 0.2, 0.2, 0.0

        for h in vector_hits:
            merged[h.id] = {
                "id": h.id,
                "score": text_w * h.score,
                "payload": h.payload,
                "sources": ["vector"],
            }
        for h in image_hits or []:
            entry = merged.get(h.id) or {
                "id": h.id,
                "score": 0.0,
                "payload": h.payload,
                "sources": [],
            }
            entry["score"] += image_w * h.score
            entry["sources"].append("image")
            merged[h.id] = entry
        for h in profile_hits or []:
            entry = merged.get(h.id) or {
                "id": h.id,
                "score": 0.0,
                "payload": h.payload,
                "sources": [],
            }
            entry["score"] += profile_w * h.score
            entry["sources"].append("profile")
            merged[h.id] = entry
        for o in content:
            key = str(o.id)
            entry = merged.get(key) or {"id": key, "score": 0.0, "payload": {}, "sources": []}
            entry["score"] += content_w * (o.rating / 5.0 + min(o.popularity / 1000.0, 1.0)) / 2
            entry["payload"] = {**(entry.get("payload") or {}), "season": o.season}
            entry["sources"].append("content")
            merged[key] = entry
        for o in collaborative:
            key = str(o.id)
            entry = merged.get(key) or {"id": key, "score": 0.0, "payload": {}, "sources": []}
            entry["score"] += collab_w
            entry["sources"].append("collaborative")
            merged[key] = entry

        if season:
            for cid, entry in merged.items():
                payload_season = (entry.get("payload") or {}).get("season")
                if payload_season == season:
                    entry["score"] *= 1.15

        ordered = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]
        return {c["id"]: c for c in ordered}

    # ----------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------- #
    async def recommend(
        self,
        user: User,
        query: str,
        filters: OutfitFilters,
        weather: dict[str, Any] | None,
        top_k: int = 6,
        image_url: str | None = None,
        hm_region: str | None = None,
        inferred_season: str | None = None,
    ) -> HybridResult:
        enriched_query = query
        if image_url:
            try:
                image_bytes = load_image_bytes(image_url)
                vision_hint = await describe_image_for_query(image_bytes)
                if vision_hint:
                    enriched_query = f"{query}. Inspiration from uploaded image: {vision_hint}"
            except Exception as exc:
                logger.warning(f"Vision query enrichment skipped: {exc}")

        # 1. candidate generation
        vector_hits = await self._vector_candidates(enriched_query, filters)
        profile_hits = await self._user_profile_candidates(user)
        image_hits = await self._image_candidates(image_url)
        content = await self._content_candidates(filters)
        collaborative = await self._collaborative_candidates(user)
        season = inferred_season or filters.season
        merged = self._merge_candidates(
            vector_hits,
            content,
            collaborative,
            image_hits=image_hits,
            profile_hits=profile_hits,
            season=season,
        )

        if not merged:
            return HybridResult(
                reasoning="No candidates matched the filters. Try broadening your query.",
                confidence=0.0,
                trend_score=0.0,
                items=[],
            )

        # 2. fetch ORM data for payload enrichment
        candidate_ids = [UUID(cid) for cid in merged.keys()]
        result = await self.db.execute(
            select(Outfit).where(Outfit.id.in_(candidate_ids))
        )
        outfits_by_id = {str(o.id): o for o in result.scalars().all()}

        candidate_blocks: list[dict[str, Any]] = []
        for cid, entry in merged.items():
            o = outfits_by_id.get(cid)
            if not o:
                continue
            candidate_blocks.append(
                {
                    "id": str(o.id),
                    "name": o.name,
                    "style": o.style,
                    "season": o.season,
                    "colors": o.colors,
                    "brand": o.brand,
                    "tags": o.tags,
                    "price": o.price,
                    "currency": o.currency,
                }
            )

        # 3. profile + RAG context
        profile = self._build_profile(user)
        kb_docs = await retrieve_context(
            enriched_query,
            user_id=str(user.id),
            top_k=4,
            user_profile=profile,
        )
        kb_block = format_kb_block(kb_docs)

        # 4. weather context
        context_block = season_context_block(weather, season, hm_region)
        if filters.occasion:
            context_block += f"\n- Occasion: {filters.occasion}"

        prompt = RECOMMENDATION_PROMPT.format(
            profile_block=render_profile(profile),
            context_block=context_block,
            kb_block=kb_block,
            candidates_block=render_candidates(candidate_blocks),
        )

        # 5. LLM re-rank
        data = await self.llm.complete_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT + language_instruction(user.locale)},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        items_raw = data.get("items") or []
        if not items_raw:
            # fallback to the merged candidates if the LLM gave nothing
            items_raw = [
                {"outfit_id": cid, "score": entry["score"], "why": "Matched your preferences."}
                for cid, entry in list(merged.items())[:top_k]
            ]
        else:
            items_raw = items_raw[:top_k]

        # ensure all referenced outfit ids exist
        items_clean: list[dict[str, Any]] = []
        for it in items_raw:
            oid = str(it.get("outfit_id", "")).strip()
            if oid in outfits_by_id:
                items_clean.append(
                    {
                        "outfit_id": oid,
                        "score": float(it.get("score") or 0.0),
                        "why": str(it.get("why") or ""),
                    }
                )

        reasoning = str(data.get("reasoning", "")).strip()
        confidence = float(data.get("confidence") or 0.7)
        trend_score = float(data.get("trend_score") or self._trend_score(items_clean, outfits_by_id))

        logger.info(
            f"Recommendation produced {len(items_clean)} items "
            f"(confidence={confidence:.2f}, trend={trend_score:.2f})"
        )
        return HybridResult(
            reasoning=reasoning or "Curated based on your preferences and current trends.",
            confidence=max(0.0, min(1.0, confidence)),
            trend_score=max(0.0, min(1.0, trend_score)),
            items=items_clean,
        )

    @staticmethod
    def _build_profile(user: User) -> dict[str, Any]:
        prefs = user.preferences or {}
        return {
            "gender": user.gender,
            "body_type": user.body_type,
            "location": user.location,
            "budget": prefs.get("budget"),
            "colors": prefs.get("colors", []),
            "brands": prefs.get("brands", []),
            "styles": prefs.get("styles", []),
        }

    @staticmethod
    def _trend_score(items: list[dict[str, Any]], outfits_by_id: dict[str, Outfit]) -> float:
        if not items:
            return 0.0
        scores: list[float] = []
        for it in items:
            o = outfits_by_id.get(str(it["outfit_id"]))
            if not o:
                continue
            scores.append(min(o.popularity / 1000.0, 1.0))
        return sum(scores) / len(scores) if scores else 0.0


# --------------------------------------------------------------------- #
# Helpers used at indexing time
# --------------------------------------------------------------------- #
def outfit_to_index_text(outfit: Outfit) -> str:
    """Compose a rich text representation for embedding."""
    parts = [
        outfit.name,
        outfit.description or "",
        f"style: {outfit.style}" if outfit.style else "",
        f"season: {outfit.season}" if outfit.season else "",
        f"gender: {outfit.gender}" if outfit.gender else "",
        f"occasion: {outfit.occasion}" if outfit.occasion else "",
        f"colors: {', '.join(outfit.colors or [])}",
        f"materials: {', '.join(outfit.materials or [])}",
        f"tags: {', '.join(outfit.tags or [])}",
        f"brand: {outfit.brand}" if outfit.brand else "",
    ]
    return ". ".join(p for p in parts if p)
