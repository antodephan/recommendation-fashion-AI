"""User and profile schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserPreferences(BaseModel):
    colors: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    budget: float | None = None
    currency: str = "USD"
    avoid: list[str] = Field(default_factory=list)


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    is_active: bool
    is_email_verified: bool
    gender: str | None
    body_type: str | None
    height_cm: int | None
    weight_kg: int | None
    location: str | None
    locale: str
    preferences: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    gender: str | None = None
    body_type: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    location: str | None = None
    locale: str | None = None
    preferences: UserPreferences | None = None


class UserAdminUpdate(UserUpdate):
    role: UserRole | None = None
    is_active: bool | None = None
