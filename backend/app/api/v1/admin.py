"""Admin endpoints (RBAC-protected)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select

from app.core.deps import DbSession, require_admin
from app.core.exceptions import NotFoundError
from app.models.analytics import ApiUsage, EventLog
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository
from app.schemas.common import Message, Page
from app.schemas.user import UserAdminUpdate, UserRead
from app.services.admin_insights_service import AdminInsightsService

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/users", response_model=Page[UserRead])
async def list_users(
    db: DbSession,
    q: str | None = None,
    role: UserRole | None = None,
    page: int = 1,
    page_size: int = 25,
):
    repo = UserRepository(db)
    items, total = await repo.list_with_filters(q=q, role=role, limit=page_size, offset=(page - 1) * page_size)
    return Page[UserRead](items=[UserRead.model_validate(u) for u in items], total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, payload: UserAdminUpdate, db: DbSession):
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundError("User not found")
    data = payload.model_dump(exclude_unset=True)
    if "preferences" in data and data["preferences"] is not None:
        data["preferences"] = data["preferences"].model_dump() if hasattr(data["preferences"], "model_dump") else data["preferences"]
    updated = await repo.update(user, **data)
    return UserRead.model_validate(updated)


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(user_id: UUID, db: DbSession):
    repo = UserRepository(db)
    if not await repo.get(user_id):
        raise NotFoundError("User not found")
    await repo.delete(user_id)
    return Message(message="user deleted")


@router.get("/overview")
async def overview(db: DbSession):
    return await AdminInsightsService(db).overview()


@router.get("/insights/overview")
async def insights_overview(db: DbSession):
    return await AdminInsightsService(db).overview()


@router.get("/insights/hm-sync")
async def insights_hm_sync(db: DbSession, days: int = Query(30, le=90)):
    return await AdminInsightsService(db).hm_sync_history(days=days)


@router.get("/insights/user-trends")
async def insights_user_trends(db: DbSession):
    return await AdminInsightsService(db).user_trends()


@router.get("/insights/fashion-trends")
async def insights_fashion_trends(db: DbSession):
    return await AdminInsightsService(db).fashion_trends()


@router.get("/insights/recommendations")
async def insights_recommendations(db: DbSession, days: int = Query(30, le=90)):
    return await AdminInsightsService(db).recommendations_series(days=days)


@router.post("/hm/sync-catalog", response_model=Message)
async def trigger_hm_catalog_sync(db: DbSession):
    from app.scripts.import_hm_catalog import import_hm_catalog

    result = await import_hm_catalog(force=True)
    return Message(message=f"H&M catalog sync complete: {result}")


@router.post("/hm/sync-trends", response_model=Message)
async def trigger_hm_trends_sync(db: DbSession):
    from app.scripts.sync_hm_trends import sync_hm_trends

    result = await sync_hm_trends()
    return Message(message=f"H&M trends sync complete: {result}")


@router.get("/usage")
async def recent_api_usage(db: DbSession, limit: int = Query(50, le=200)):
    rows = await db.execute(select(ApiUsage).order_by(desc(ApiUsage.created_at)).limit(limit))
    return [
        {
            "id": str(u.id),
            "user_id": str(u.user_id) if u.user_id else None,
            "endpoint": u.endpoint,
            "method": u.method,
            "status_code": u.status_code,
            "latency_ms": u.latency_ms,
            "tokens_used": u.tokens_used,
            "model": u.model,
            "cost_usd": u.cost_usd,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows.scalars().all()
    ]


@router.get("/events")
async def recent_events(db: DbSession, limit: int = Query(50, le=200)):
    rows = await db.execute(select(EventLog).order_by(desc(EventLog.created_at)).limit(limit))
    return [
        {
            "id": str(e.id),
            "user_id": str(e.user_id) if e.user_id else None,
            "event": e.event,
            "properties": e.properties,
            "created_at": e.created_at.isoformat(),
        }
        for e in rows.scalars().all()
    ]
