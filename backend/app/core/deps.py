"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Sequence
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the user from a Bearer token, supporting cookies as fallback."""
    raw_token = token
    if not raw_token and authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1]
    if not raw_token:
        raw_token = request.cookies.get("access_token")
    if not raw_token:
        raise UnauthorizedError("Missing access token")

    payload = decode_token(raw_token, expected_type="access")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Invalid token subject")

    try:
        user_id = UUID(user_id_str)
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Return the authenticated user when a valid token is present, else None."""
    raw_token = token
    if not raw_token and authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1]
    if not raw_token:
        raw_token = request.cookies.get("access_token")
    if not raw_token:
        return None

    try:
        payload = decode_token(raw_token, expected_type="access")
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = UUID(user_id_str)
    except Exception:
        return None

    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user or not user.is_active:
        return None
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole):
    """Dependency factory enforcing RBAC."""
    allowed: Sequence[UserRole] = roles or ()

    async def _checker(user: CurrentUser) -> User:
        if allowed and user.role not in allowed:
            raise ForbiddenError(f"Requires role(s): {', '.join(r.value for r in allowed)}")
        return user

    return _checker


require_admin = require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)
require_superadmin = require_roles(UserRole.SUPERADMIN)
