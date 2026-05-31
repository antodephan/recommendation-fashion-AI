"""Password hashing and JWT token utilities."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import UnauthorizedError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh", "verify", "reset"]


# --------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# --------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------- #
def _expiry_for(token_type: TokenType) -> datetime:
    now = datetime.now(timezone.utc)
    if token_type == "access":
        return now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    if token_type == "refresh":
        return now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    if token_type == "verify":
        return now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    if token_type == "reset":
        return now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    return now + timedelta(minutes=15)


def create_token(
    subject: str | int,
    token_type: TokenType = "access",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT for the given subject (user id)."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(_expiry_for(token_type).timestamp()),
        "type": token_type,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT. Raises `UnauthorizedError` on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise UnauthorizedError("Invalid token type")

    return payload


def create_token_pair(subject: str | int, extra_claims: dict[str, Any] | None = None) -> tuple[str, str]:
    """Return an `(access_token, refresh_token)` pair."""
    return (
        create_token(subject, "access", extra_claims),
        create_token(subject, "refresh", extra_claims),
    )
