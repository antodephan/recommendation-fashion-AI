"""Chat-related schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.chat import MessageRole


class ConversationCreate(BaseModel):
    title: str | None = "New conversation"


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str
    pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str
    image_url: str | None = None
    conversation_id: uuid.UUID | None = None


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    image_url: str | None
    tokens: int
    extra: dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
