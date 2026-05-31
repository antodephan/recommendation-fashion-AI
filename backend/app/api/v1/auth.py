"""Authentication endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import ValidationError
from app.core.rate_limit import rate_limit
from app.schemas.auth import (
    EmailVerifyConfirm,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter()


def _set_auth_cookies(response: Response, access: str, refresh: str) -> Response:
    secure = settings.COOKIE_SECURE
    response.set_cookie(
        "access_token", access,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        "refresh_token", refresh,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return response


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_AUTH, scope="register"))],
)
async def register(payload: RegisterRequest, db: DbSession):
    service = AuthService(db)
    user = await service.register(payload.email, payload.password, payload.full_name, payload.locale)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_AUTH, scope="login"))],
)
async def login(payload: LoginRequest, request: Request, response: Response, db: DbSession):
    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    access, refresh = await service.issue_tokens(
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, response: Response, db: DbSession):
    service = AuthService(db)
    access, refresh = await service.refresh_tokens(payload.refresh_token)
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", response_model=Message)
async def logout(payload: RefreshRequest, response: Response, db: DbSession):
    service = AuthService(db)
    await service.revoke_refresh(payload.refresh_token)
    response.delete_cookie("access_token", domain=settings.COOKIE_DOMAIN, path="/")
    response.delete_cookie("refresh_token", domain=settings.COOKIE_DOMAIN, path="/")
    return Message(message="logged out")


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser):
    return user


@router.post("/password-reset/request", response_model=Message)
async def request_password_reset(payload: PasswordResetRequest, bg: BackgroundTasks, db: DbSession):
    service = AuthService(db)
    bg.add_task(service.request_password_reset, payload.email)
    return Message(message="If the email exists, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=Message)
async def confirm_password_reset(payload: PasswordResetConfirm, db: DbSession):
    service = AuthService(db)
    await service.confirm_password_reset(payload.token, payload.new_password)
    return Message(message="Password updated")


@router.post("/email/verify", response_model=Message)
async def verify_email(payload: EmailVerifyConfirm, db: DbSession):
    service = AuthService(db)
    await service.verify_email(payload.token)
    return Message(message="Email verified")


# --------------------------------------------------------------------- #
# OAuth — Google + Facebook (PKCE-friendly authorization code flow)
# --------------------------------------------------------------------- #
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v2/userinfo"

FACEBOOK_AUTH = "https://www.facebook.com/v18.0/dialog/oauth"
FACEBOOK_TOKEN = "https://graph.facebook.com/v18.0/oauth/access_token"
FACEBOOK_USERINFO = "https://graph.facebook.com/me"


@router.get("/oauth/google/login")
async def google_login():
    if not settings.GOOGLE_CLIENT_ID:
        raise ValidationError("Google OAuth not configured")
    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    return RedirectResponse(f"{GOOGLE_AUTH}?{params}")


@router.get("/oauth/google/callback")
async def google_callback(code: str, db: DbSession):
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        token_data: dict[str, Any] = token_resp.json()
        user_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_resp.raise_for_status()
        profile = user_resp.json()

    service = AuthService(db)
    user = await service.upsert_oauth_user(
        provider="google",
        provider_account_id=str(profile["id"]),
        email=profile["email"],
        full_name=profile.get("name"),
        avatar_url=profile.get("picture"),
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        raw_profile=profile,
    )
    access, refresh = await service.issue_tokens(user)
    redirect = RedirectResponse(
        f"http://localhost:3000/chat?access_token={access}&refresh_token={refresh}"
    )
    _set_auth_cookies(redirect, access, refresh)
    return redirect


@router.get("/oauth/facebook/login")
async def facebook_login():
    if not settings.FACEBOOK_CLIENT_ID:
        raise ValidationError("Facebook OAuth not configured")
    params = (
        f"client_id={settings.FACEBOOK_CLIENT_ID}"
        f"&redirect_uri={settings.FACEBOOK_REDIRECT_URI}"
        "&response_type=code"
        "&scope=email,public_profile"
    )
    return RedirectResponse(f"{FACEBOOK_AUTH}?{params}")


@router.get("/oauth/facebook/callback")
async def facebook_callback(code: str, db: DbSession):
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.get(
            FACEBOOK_TOKEN,
            params={
                "client_id": settings.FACEBOOK_CLIENT_ID,
                "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                "redirect_uri": settings.FACEBOOK_REDIRECT_URI,
                "code": code,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        user_resp = await client.get(
            FACEBOOK_USERINFO,
            params={"fields": "id,name,email,picture", "access_token": token_data["access_token"]},
        )
        user_resp.raise_for_status()
        profile = user_resp.json()

    service = AuthService(db)
    user = await service.upsert_oauth_user(
        provider="facebook",
        provider_account_id=str(profile["id"]),
        email=profile.get("email") or f"fb_{profile['id']}@example.com",
        full_name=profile.get("name"),
        avatar_url=(profile.get("picture") or {}).get("data", {}).get("url"),
        access_token=token_data.get("access_token"),
        refresh_token=None,
        raw_profile=profile,
    )
    access, refresh = await service.issue_tokens(user)
    redirect = RedirectResponse(
        f"http://localhost:3000/chat?access_token={access}&refresh_token={refresh}"
    )
    _set_auth_cookies(redirect, access, refresh)
    return redirect
