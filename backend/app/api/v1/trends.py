"""Fashion trends endpoints."""

from __future__ import annotations

from sqlalchemy import case, select

from fastapi import APIRouter, Query

from app.core.deps import DbSession
from app.models.trend import FashionTrend

router = APIRouter()


@router.get("")
async def list_trends(db: DbSession, season: str | None = Query(default=None), limit: int = 30):
    stmt = (
        select(FashionTrend)
        .order_by(
            case((FashionTrend.source == "H&M", 0), else_=1),
            FashionTrend.published_at.desc().nullslast(),
            FashionTrend.popularity.desc(),
            FashionTrend.created_at.desc(),
        )
        .limit(limit)
    )
    if season:
        stmt = stmt.where(FashionTrend.season == season)
    rows = await db.execute(stmt)
    items = list(rows.scalars().all())
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "summary": t.summary,
            "image_url": t.image_url,
            "source": t.source,
            "source_url": t.source_url,
            "tags": t.tags,
            "season": t.season,
            "popularity": t.popularity,
            "published_at": t.published_at.isoformat() if t.published_at else None,
        }
        for t in items
    ]
