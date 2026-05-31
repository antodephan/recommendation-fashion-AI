"""Lightweight analytics service — event logging + aggregate queries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import ApiUsage, EventLog
from app.models.outfit import FavoriteOutfit, Outfit
from app.models.recommendation import Recommendation, RecommendationFeedback
from app.models.user import User


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log_event(self, user_id: UUID | None, event: str, properties: dict[str, Any] | None = None) -> None:
        ev = EventLog(user_id=user_id, event=event, properties=properties or {})
        self.db.add(ev)
        await self.db.commit()

    async def record_api_usage(
        self,
        user_id: UUID | None,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        tokens_used: int = 0,
        model: str | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        usage = ApiUsage(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model=model,
            cost_usd=cost_usd,
        )
        self.db.add(usage)
        await self.db.commit()

    # -------------------------------------------------------------- #
    # Aggregations used by the admin dashboard
    # -------------------------------------------------------------- #
    async def overview(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)

        total_users = await self.db.scalar(select(func.count(User.id))) or 0
        new_users_24h = await self.db.scalar(
            select(func.count(User.id)).where(User.created_at >= since_24h)
        ) or 0
        total_recommendations = await self.db.scalar(select(func.count(Recommendation.id))) or 0
        recs_24h = await self.db.scalar(
            select(func.count(Recommendation.id)).where(Recommendation.created_at >= since_24h)
        ) or 0
        total_favorites = await self.db.scalar(select(func.count(FavoriteOutfit.id))) or 0
        total_outfits = await self.db.scalar(select(func.count(Outfit.id))) or 0
        tokens_24h = await self.db.scalar(
            select(func.coalesce(func.sum(ApiUsage.tokens_used), 0)).where(ApiUsage.created_at >= since_24h)
        ) or 0
        cost_7d = await self.db.scalar(
            select(func.coalesce(func.sum(ApiUsage.cost_usd), 0.0)).where(ApiUsage.created_at >= since_7d)
        ) or 0.0

        return {
            "users": {"total": int(total_users), "new_24h": int(new_users_24h)},
            "recommendations": {"total": int(total_recommendations), "last_24h": int(recs_24h)},
            "favorites": int(total_favorites),
            "outfits": int(total_outfits),
            "ai": {"tokens_24h": int(tokens_24h), "cost_7d": float(cost_7d)},
        }

    async def daily_active_users(self, days: int = 14) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                func.date(EventLog.created_at).label("day"),
                func.count(func.distinct(EventLog.user_id)).label("dau"),
            )
            .where(EventLog.created_at >= since)
            .group_by("day")
            .order_by("day")
        )
        rows = await self.db.execute(stmt)
        return [{"day": str(r.day), "dau": int(r.dau)} for r in rows.all()]

    async def popular_styles(self, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(Outfit.style, func.count(FavoriteOutfit.id).label("favs"))
            .join(FavoriteOutfit, FavoriteOutfit.outfit_id == Outfit.id)
            .where(Outfit.style.isnot(None))
            .group_by(Outfit.style)
            .order_by(func.count(FavoriteOutfit.id).desc())
            .limit(limit)
        )
        rows = await self.db.execute(stmt)
        # Use "name" not "style" — Recharts treats payload.style as React's style prop.
        return [{"name": r.style, "favorites": int(r.favs)} for r in rows.all()]

    async def click_through_rate(self) -> float:
        """Share of recommendation sessions with at least one item engagement."""
        total = await self.db.scalar(select(func.count(Recommendation.id))) or 0
        if not total:
            return 0.0

        clicked_direct = await self.db.scalar(
            select(func.count(Recommendation.id)).where(Recommendation.clicked_count > 0)
        ) or 0
        engaged_via_feedback = await self.db.scalar(
            select(func.count(func.distinct(RecommendationFeedback.recommendation_id))).where(
                RecommendationFeedback.label.in_(("click", "save", "favorite", "view"))
            )
        ) or 0
        # Union approximation: use max of the two counters (feedback also bumps clicked_count now).
        engaged = max(int(clicked_direct), int(engaged_via_feedback))
        return min(1.0, engaged / total)
