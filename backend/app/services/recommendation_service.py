"""Recommendation service connecting the engine to repos + persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.recommendation import Recommendation
from app.models.user import User
from app.repositories.outfit_repo import OutfitRepository, RecommendationRepository
from app.schemas.outfit import (
    OutfitFilters,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.hm_client import HMClient
from app.services.preference_service import PreferenceService
from app.services.season_service import infer_season
from app.services.weather_service import WeatherService
from app.utils.gender import normalize_gender
from app.utils.style_matching import primary_canonical_style, resolve_canonical_styles

from ai_engine.recommender import RecommendationEngine


class RecommendationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.outfits = OutfitRepository(db)
        self.recs = RecommendationRepository(db)
        self.engine = RecommendationEngine(db)
        self.weather = WeatherService()
        self.analytics = AnalyticsService(db)
        self.preferences = PreferenceService(db)

    async def _resolve_hm_region(self, user: User) -> str:
        prefs = user.preferences or {}
        if prefs.get("hm_region"):
            return str(prefs["hm_region"])
        try:
            region = await HMClient().resolve_region()
            prefs["hm_region"] = region
            user.preferences = prefs
            await self.db.commit()
            return region
        except Exception:
            return "vn"

    @staticmethod
    def _apply_user_filters(user: User, filters: OutfitFilters) -> OutfitFilters:
        """Merge profile gender, styles, budget into request filters."""
        prefs = user.preferences or {}
        if not filters.gender and user.gender:
            filters.gender = normalize_gender(user.gender)
        if not filters.style:
            styles = prefs.get("styles") or []
            if styles:
                filters.style = primary_canonical_style(styles) or str(styles[0]).lower()
                # Keep tag hints for vector search when style is Vietnamese free-text
                extra_tags = resolve_canonical_styles(styles)
                if extra_tags:
                    filters.tags = list(dict.fromkeys([*filters.tags, *extra_tags]))
        if filters.max_price is None and prefs.get("budget"):
            try:
                filters.max_price = float(prefs["budget"])
            except (TypeError, ValueError):
                pass
        return filters

    async def recommend(self, user: User, req: RecommendationRequest) -> RecommendationResponse:
        filters = self._apply_user_filters(user, req.filters or OutfitFilters())
        location = req.location or user.location or "Ho Chi Minh City"
        weather = (
            await self.weather.current(location)
            if req.use_weather
            else None
        )
        inferred_season = filters.season
        if not inferred_season:
            temp = weather.get("temp_c") if weather else None
            inferred_season = infer_season(temp, location=location)
            filters.season = inferred_season

        hm_region = await self._resolve_hm_region(user)
        result = await self.engine.recommend(
            user,
            req.query,
            filters,
            weather,
            top_k=req.top_k,
            image_url=req.image_url,
            hm_region=hm_region,
            inferred_season=inferred_season,
        )

        outfits = await self.outfits.get_many([UUID(i["outfit_id"]) for i in result.items])
        outfits_by_id = {str(o.id): o for o in outfits}

        items: list[RecommendationItem] = []
        for it in result.items:
            o = outfits_by_id.get(it["outfit_id"])
            if not o:
                continue
            items.append(
                RecommendationItem(
                    outfit_id=o.id,
                    name=o.name,
                    image_url=o.image_url,
                    score=it["score"],
                    why=it["why"],
                    tags=o.tags or [],
                    price=o.price,
                    currency=o.currency,
                    source_url=o.source_url,
                )
            )

        rec = await self.recs.create(
            user_id=user.id,
            conversation_id=req.conversation_id,
            query=req.query,
            reasoning=result.reasoning,
            confidence=result.confidence,
            trend_score=result.trend_score,
            payload={
                "items": [it.model_dump(mode="json") for it in items],
                "weather": weather,
                "season": inferred_season,
                "hm_region": hm_region,
            },
            source="hybrid",
        )
        await self.analytics.log_event(
            user.id,
            "recommendation_generated",
            {"id": str(rec.id), "items": len(items), "confidence": result.confidence},
        )

        return RecommendationResponse(
            id=rec.id,
            query=rec.query,
            reasoning=rec.reasoning,
            confidence=rec.confidence,
            trend_score=rec.trend_score,
            items=items,
            weather=weather,
            created_at=rec.created_at,
        )

    async def history(self, user: User, limit: int = 30) -> list[Recommendation]:
        return await self.recs.list_for_user(user.id, limit=limit)

    async def feedback(
        self,
        user: User,
        recommendation_id: UUID,
        rating: int,
        label: str | None,
        comment: str | None,
    ) -> None:
        rec = await self.recs.get(recommendation_id)
        if not rec or rec.user_id != user.id:
            raise NotFoundError("Recommendation not found")
        await self.recs.add_feedback(rec.id, user.id, rating, label, comment)
        if label in ("click", "save", "favorite", "view"):
            rec.clicked_count = (rec.clicked_count or 0) + 1
            await self.db.commit()
        await self.preferences.refresh_profile_vector(user)
        await self.analytics.log_event(
            user.id,
            "recommendation_feedback",
            {"rec": str(rec.id), "rating": rating, "label": label},
        )
