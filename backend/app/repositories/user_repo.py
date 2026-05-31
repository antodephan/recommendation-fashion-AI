"""User repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.user import OAuthAccount, User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_with_oauth(self, user_id: UUID) -> User | None:
        result = await self.db.execute(
            select(User).options(selectinload(User.oauth_accounts)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        q: str | None = None,
        role: UserRole | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.full_name).like(like))
        if role:
            stmt = stmt.where(User.role == role)

        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = (await self.db.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))).scalars().all()
        return list(rows), int(total or 0)

    async def upsert_oauth(
        self,
        user: User,
        provider: str,
        provider_account_id: str,
        access_token: str | None,
        refresh_token: str | None,
        raw_profile: dict,
    ) -> OAuthAccount:
        result = await self.db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        oauth = result.scalar_one_or_none()
        if oauth is None:
            oauth = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_account_id=provider_account_id,
                access_token=access_token,
                refresh_token=refresh_token,
                raw_profile=raw_profile,
            )
            self.db.add(oauth)
        else:
            oauth.access_token = access_token
            oauth.refresh_token = refresh_token
            oauth.raw_profile = raw_profile
        await self.db.commit()
        await self.db.refresh(oauth)
        return oauth
