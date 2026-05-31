"""Outfit catalog + favorites endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError
from app.repositories.outfit_repo import FavoriteRepository, OutfitRepository
from app.schemas.common import Message, Page
from app.schemas.outfit import OutfitFilters, OutfitRead

router = APIRouter()


@router.get("", response_model=Page[OutfitRead])
async def list_outfits(
    db: DbSession,
    style: str | None = Query(default=None),
    season: str | None = Query(default=None),
    gender: str | None = Query(default=None),
    occasion: str | None = Query(default=None),
    color: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    max_price: float | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
):
    filters = OutfitFilters(
        style=style, season=season, gender=gender, occasion=occasion,
        color=color, brand=brand, max_price=max_price, query=q,
    )
    repo = OutfitRepository(db)
    items, total = await repo.search(filters, limit=page_size, offset=(page - 1) * page_size)
    return Page[OutfitRead](items=[OutfitRead.model_validate(o) for o in items], total=total, page=page, page_size=page_size)


@router.get("/trending", response_model=list[OutfitRead])
async def trending(db: DbSession, limit: int = 12):
    repo = OutfitRepository(db)
    items = await repo.trending(limit=limit)
    return [OutfitRead.model_validate(o) for o in items]


@router.get("/{outfit_id}", response_model=OutfitRead)
async def get_outfit(outfit_id: UUID, db: DbSession):
    repo = OutfitRepository(db)
    outfit = await repo.get(outfit_id)
    if not outfit:
        raise NotFoundError("Outfit not found")
    return OutfitRead.model_validate(outfit)


@router.get("/me/favorites", response_model=list[OutfitRead])
async def my_favorites(user: CurrentUser, db: DbSession):
    repo = FavoriteRepository(db)
    favs = await repo.list_for_user(user.id)
    return [OutfitRead.model_validate(f.outfit) for f in favs]


@router.post("/{outfit_id}/favorite", response_model=Message)
async def toggle_favorite(outfit_id: UUID, user: CurrentUser, db: DbSession):
    repo = FavoriteRepository(db)
    added = await repo.toggle(user.id, outfit_id)
    return Message(message="added" if added else "removed")
