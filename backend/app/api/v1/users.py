"""User self-service endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserRead, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession):
    repo = UserRepository(db)
    data = payload.model_dump(exclude_unset=True)
    if "preferences" in data and data["preferences"] is not None:
        data["preferences"] = data["preferences"].model_dump() if hasattr(data["preferences"], "model_dump") else data["preferences"]
    updated = await repo.update(user, **data)
    return updated
