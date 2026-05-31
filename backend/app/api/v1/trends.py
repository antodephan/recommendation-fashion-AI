"""Fashion trends endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbSession
from app.services.trend_service import TrendService, current_season

router = APIRouter()


@router.get("")
async def list_trends(
    db: DbSession,
    season: str | None = Query(default=None, description="Filter by fashion season"),
    limit: int = Query(default=12, ge=1, le=30),
):
    """Style trends for the season — editorial cards, not H&M product listings."""
    service = TrendService(db)
    items = await service.list_style_trends(season=season or current_season(), limit=limit)
    return {"season": season or current_season(), "items": items}


@router.get("/{trend_id}/outfits")
async def trend_outfits(
    trend_id: UUID,
    db: DbSession,
    limit: int = Query(default=8, ge=1, le=16),
):
    """H&M outfit picks for a style trend — loaded after the user clicks."""
    service = TrendService(db)
    return await service.get_trend_outfits(trend_id, limit=limit)
