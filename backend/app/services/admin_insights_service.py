"""Admin dashboard aggregations for H&M sync, user trends, and fashion trends."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import EventLog
from app.models.outfit import Outfit
from app.models.recommendation import Recommendation
from app.models.sync_run import SyncJobType, SyncRun, SyncStatus
from app.models.trend import FashionTrend
from app.models.user import User
from app.services.analytics_service import AnalyticsService


class AdminInsightsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)

    async def overview(self) -> dict[str, Any]:
        base = await self.analytics.overview()
        hm_products = await self.db.scalar(
            select(func.count(Outfit.id)).where(Outfit.brand == "H&M")
        ) or 0
        active_trends = await self.db.scalar(
            select(func.count(FashionTrend.id)).where(FashionTrend.source == "H&M")
        ) or 0
        last_sync = await self.db.execute(
            select(SyncRun).order_by(desc(SyncRun.created_at)).limit(1)
        )
        last = last_sync.scalar_one_or_none()
        chat_recs = await self._chat_to_rec_rate()
        return {
            **base,
            "hm": {
                "products": int(hm_products),
                "trends": int(active_trends),
                "last_sync_at": last.created_at.isoformat() if last else None,
                "last_sync_region": last.region if last else None,
                "last_sync_job": last.job_type.value if last else None,
                "last_sync_status": last.status.value if last else None,
                "last_sync_error": last.error_message if last else None,
            },
            "chat_to_recommendation_rate": chat_recs,
            "ctr": await self.analytics.click_through_rate(),
        }

    async def hm_sync_history(self, days: int = 30) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await self.db.execute(
            select(SyncRun)
            .where(SyncRun.created_at >= since)
            .order_by(SyncRun.created_at)
        )
        return [
            {
                "id": str(r.id),
                "job_type": r.job_type.value,
                "status": r.status.value,
                "region": r.region,
                "items_added": r.items_added,
                "items_updated": r.items_updated,
                "items_failed": r.items_failed,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat(),
                "error_message": r.error_message,
            }
            for r in rows.scalars().all()
        ]

    async def user_trends(self) -> dict[str, Any]:
        users = await self.db.execute(select(User))
        color_c: Counter[str] = Counter()
        style_c: Counter[str] = Counter()
        brand_c: Counter[str] = Counter()
        location_c: Counter[str] = Counter()
        budgets: list[float] = []

        for u in users.scalars().all():
            prefs = u.preferences or {}
            for c in prefs.get("colors") or []:
                color_c[str(c).lower()] += 1
            for s in prefs.get("styles") or []:
                style_c[str(s).lower()] += 1
            for b in prefs.get("brands") or []:
                brand_c[str(b).lower()] += 1
            if u.location:
                location_c[u.location] += 1
            try:
                if prefs.get("budget"):
                    budgets.append(float(prefs["budget"]))
            except (TypeError, ValueError):
                pass

        since = datetime.now(timezone.utc) - timedelta(days=14)
        pref_events = await self.db.execute(
            select(EventLog)
            .where(EventLog.event == "preference_updated", EventLog.created_at >= since)
            .order_by(EventLog.created_at)
        )
        pref_timeline: dict[str, int] = {}
        for ev in pref_events.scalars().all():
            day = ev.created_at.date().isoformat()
            pref_timeline[day] = pref_timeline.get(day, 0) + 1

        return {
            "top_colors": [{"name": k, "count": v} for k, v in color_c.most_common(10)],
            "top_styles": [{"name": k, "count": v} for k, v in style_c.most_common(10)],
            "top_brands": [{"name": k, "count": v} for k, v in brand_c.most_common(10)],
            "locations": [{"name": k, "count": v} for k, v in location_c.most_common(10)],
            "budget_avg": sum(budgets) / len(budgets) if budgets else None,
            "preference_signals": [{"day": d, "count": c} for d, c in sorted(pref_timeline.items())],
        }

    async def fashion_trends(self) -> dict[str, Any]:
        rows = await self.db.execute(
            select(FashionTrend).order_by(desc(FashionTrend.popularity), desc(FashionTrend.created_at))
        )
        trends = list(rows.scalars().all())
        season_c: Counter[str] = Counter()
        tag_c: Counter[str] = Counter()
        ranking: list[dict[str, Any]] = []
        timeline: dict[str, int] = {}

        for t in trends:
            if t.season:
                season_c[t.season] += 1
            for tag in t.tags or []:
                tag_c[tag] += 1
            ranking.append(
                {
                    "title": t.title,
                    "popularity": t.popularity,
                    "season": t.season,
                    "source": t.source,
                }
            )
            day = (t.published_at or t.created_at).date().isoformat()
            timeline[day] = timeline.get(day, 0) + 1

        return {
            "ranking": ranking[:15],
            "by_season": [{"name": k, "count": v} for k, v in season_c.most_common()],
            "top_tags": [{"name": k, "count": v} for k, v in tag_c.most_common(12)],
            "timeline": [{"day": d, "count": c} for d, c in sorted(timeline.items())],
        }

    async def recommendations_series(self, days: int = 30) -> list[dict[str, Any]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = await self.db.execute(
            select(
                func.date(Recommendation.created_at).label("day"),
                func.count(Recommendation.id).label("count"),
                func.avg(Recommendation.confidence).label("avg_confidence"),
                func.avg(Recommendation.trend_score).label("avg_trend"),
            )
            .where(Recommendation.created_at >= since)
            .group_by("day")
            .order_by("day")
        )
        return [
            {
                "day": str(r.day),
                "count": int(r.count),
                "avg_confidence": float(r.avg_confidence or 0),
                "avg_trend": float(r.avg_trend or 0),
            }
            for r in rows.all()
        ]

    async def _chat_to_rec_rate(self) -> float:
        chats = await self.db.scalar(
            select(func.count(EventLog.id)).where(EventLog.event == "chat_message")
        ) or 0
        recs = await self.db.scalar(
            select(func.count(EventLog.id)).where(EventLog.event == "recommendation_generated")
        ) or 0
        if not chats:
            return 0.0
        return min(1.0, recs / chats)
