"""Authentication & account lifecycle service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.core.logger import logger
from app.core.security import (
    create_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.token import AuthCode, RefreshToken
from app.models.user import User, UserRole
from app.repositories.user_repo import UserRepository
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.emailer = EmailService()

    # ---------- Registration / login ----------
    async def register(
        self, email: str, password: str, full_name: str | None, locale: str | None = "en"
    ) -> User:
        email = email.lower().strip()
        if await self.users.get_by_email(email):
            raise ConflictError("Email is already registered")
        loc = (locale or "en").lower()
        if not loc.startswith("vi"):
            loc = "en"
        user = await self.users.create(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.USER,
            locale=loc,
        )
        await self._send_verification_email(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email.lower().strip())
        if not user or not user.hashed_password:
            raise UnauthorizedError("Invalid credentials")
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid credentials")
        if not user.is_active:
            raise UnauthorizedError("Account disabled")
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ---------- Tokens ----------
    async def issue_tokens(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, str]:
        access, refresh = create_token_pair(
            user.id, extra_claims={"role": user.role.value, "email": user.email}
        )
        payload = decode_token(refresh, expected_type="refresh")
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        rt = RefreshToken(
            user_id=user.id,
            jti=payload["jti"],
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.db.add(rt)
        await self.db.commit()
        return access, refresh

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedError("Invalid refresh token")

        result = await self.db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        rt = result.scalar_one_or_none()
        if not rt or rt.revoked or rt.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("Refresh token expired or revoked")

        # rotation
        rt.revoked = True
        await self.db.commit()

        user = await self.users.get(rt.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Account no longer active")
        return await self.issue_tokens(user)

    async def revoke_refresh(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except UnauthorizedError:
            return
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await self.db.commit()

    # ---------- Email verification ----------
    async def _create_auth_code(self, user: User, purpose: str, ttl_minutes: int) -> str:
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        ac = AuthCode(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
        self.db.add(ac)
        await self.db.commit()
        return raw

    async def _consume_auth_code(self, token: str, purpose: str) -> User:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await self.db.execute(
            select(AuthCode).where(AuthCode.token_hash == token_hash, AuthCode.purpose == purpose)
        )
        code = result.scalar_one_or_none()
        if not code or code.used or code.expires_at < datetime.now(timezone.utc):
            raise ValidationError("Token invalid or expired")
        user = await self.users.get(code.user_id)
        if not user:
            raise NotFoundError("User not found")
        code.used = True
        await self.db.commit()
        return user

    async def _send_verification_email(self, user: User) -> None:
        token = await self._create_auth_code(
            user, "verify_email", settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS * 60
        )
        link = f"http://localhost:3000/verify-email?token={token}"
        await self.emailer.send(
            to=user.email,
            subject="Verify your Couture AI email",
            body=(
                f"Welcome to Couture AI!\n\nPlease verify your email by clicking the link below:\n{link}\n"
            ),
        )
        logger.info(f"Verification email queued for {user.email}")

    async def verify_email(self, token: str) -> User:
        user = await self._consume_auth_code(token, "verify_email")
        user.is_email_verified = True
        await self.db.commit()
        return user

    # ---------- Password reset ----------
    async def request_password_reset(self, email: str) -> None:
        user = await self.users.get_by_email(email.lower().strip())
        if not user:
            # Avoid revealing whether the email exists.
            logger.info(f"Password reset requested for unknown email: {email}")
            return
        token = await self._create_auth_code(
            user, "reset_password", settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        link = f"http://localhost:3000/reset-password?token={token}"
        await self.emailer.send(
            to=user.email,
            subject="Reset your Couture AI password",
            body=f"Click the link below to reset your password:\n{link}\n",
        )

    async def confirm_password_reset(self, token: str, new_password: str) -> User:
        user = await self._consume_auth_code(token, "reset_password")
        user.hashed_password = hash_password(new_password)
        await self.db.commit()
        return user

    # ---------- OAuth ----------
    async def upsert_oauth_user(
        self,
        provider: str,
        provider_account_id: str,
        email: str,
        full_name: str | None,
        avatar_url: str | None,
        access_token: str | None,
        refresh_token: str | None,
        raw_profile: dict,
    ) -> User:
        email = email.lower().strip()
        user = await self.users.get_by_email(email)
        if not user:
            user = await self.users.create(
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                is_email_verified=True,
                role=UserRole.USER,
            )
        else:
            updates = {}
            if not user.avatar_url and avatar_url:
                updates["avatar_url"] = avatar_url
            if not user.full_name and full_name:
                updates["full_name"] = full_name
            if updates:
                await self.users.update(user, **updates)
        await self.users.upsert_oauth(user, provider, provider_account_id, access_token, refresh_token, raw_profile)
        return user
