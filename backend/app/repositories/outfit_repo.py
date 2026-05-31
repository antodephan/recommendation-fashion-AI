"""Outfit, favorite and recommendation repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from app.models.outfit import FavoriteOutfit, Outfit
from app.models.recommendation import Recommendation, RecommendationFeedback
from app.repositories.base import BaseRepository
from app.schemas.outfit import OutfitFilters


class OutfitRepository(BaseRepository[Outfit]):
    model = Outfit

    async def search(
        self, filters: OutfitFilters, limit: int = 50, offset: int = 0
    ) -> tuple[list[Outfit], int]:
        conditions = [Outfit.is_active.is_(True)]
        if filters.style:
            conditions.append(Outfit.style == filters.style)
        if filters.season:
            conditions.append(Outfit.season == filters.season)
        if filters.gender:
            conditions.append(Outfit.gender == filters.gender)
        if filters.occasion:
            conditions.append(Outfit.occasion == filters.occasion)
        if filters.body_type:
            conditions.append(Outfit.body_type == filters.body_type)
        if filters.brand:
            conditions.append(Outfit.brand.ilike(f"%{filters.brand}%"))
        if filters.max_price is not None:
            conditions.append(Outfit.price <= filters.max_price)
        if filters.color:
            conditions.append(Outfit.colors.any(filters.color))
        if filters.query:
            like = f"%{filters.query.lower()}%"
            conditions.append(
                func.lower(Outfit.name).like(like) | func.lower(Outfit.description).like(like)
            )

        stmt = select(Outfit).where(and_(*conditions))
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = await self.db.execute(
            stmt.options(selectinload(Outfit.items))
            .order_by(Outfit.popularity.desc(), Outfit.rating.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows.scalars().all()), int(total or 0)

    async def get_many(self, ids: list[UUID]) -> list[Outfit]:
        if not ids:
            return []
        result = await self.db.execute(
            select(Outfit).options(selectinload(Outfit.items)).where(Outfit.id.in_(ids))
        )
        return list(result.scalars().all())

    async def trending(self, limit: int = 12) -> list[Outfit]:
        result = await self.db.execute(
            select(Outfit)
            .options(selectinload(Outfit.items))
            .where(Outfit.is_active.is_(True))
            .order_by(Outfit.popularity.desc(), Outfit.rating.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class FavoriteRepository(BaseRepository[FavoriteOutfit]):
    model = FavoriteOutfit

    async def list_for_user(self, user_id: UUID) -> list[FavoriteOutfit]:
        result = await self.db.execute(
            select(FavoriteOutfit)
            .options(selectinload(FavoriteOutfit.outfit).selectinload(Outfit.items))
            .where(FavoriteOutfit.user_id == user_id)
            .order_by(FavoriteOutfit.created_at.desc())
        )
        return list(result.scalars().all())

    async def toggle(self, user_id: UUID, outfit_id: UUID) -> bool:
        """Return True if added, False if removed."""
        existing = await self.db.execute(
            select(FavoriteOutfit).where(
                FavoriteOutfit.user_id == user_id, FavoriteOutfit.outfit_id == outfit_id
            )
        )
        fav = existing.scalar_one_or_none()
        if fav:
            await self.db.delete(fav)
            await self.db.commit()
            return False
        await self.create(user_id=user_id, outfit_id=outfit_id)
        return True


class RecommendationRepository(BaseRepository[Recommendation]):
    model = Recommendation

    async def list_for_user(self, user_id: UUID, limit: int = 30) -> list[Recommendation]:
        result = await self.db.execute(
            select(Recommendation)
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_feedback(
        self, recommendation_id: UUID, user_id: UUID, rating: int, label: str | None, comment: str | None
    ) -> RecommendationFeedback:
        fb = RecommendationFeedback(
            recommendation_id=recommendation_id,
            user_id=user_id,
            rating=rating,
            label=label,
            comment=comment,
        )
        self.db.add(fb)
        await self.db.commit()
        await self.db.refresh(fb)
        return fb
