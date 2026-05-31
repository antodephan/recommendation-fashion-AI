"""Analytics endpoints (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import DbSession, require_admin
from app.services.analytics_service import AnalyticsService

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview(db: DbSession):
    return await AnalyticsService(db).overview()


@router.get("/dau")
async def dau(db: DbSession, days: int = 14):
    return await AnalyticsService(db).daily_active_users(days=days)


@router.get("/popular-styles")
async def popular_styles(db: DbSession, limit: int = 10):
    return await AnalyticsService(db).popular_styles(limit=limit)


@router.get("/ctr")
async def click_through_rate(db: DbSession):
    return {"ctr": await AnalyticsService(db).click_through_rate()}
