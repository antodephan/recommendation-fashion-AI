"""Chat repositories: conversations + messages."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message, MessageRole
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def list_for_user(self, user_id: UUID, limit: int = 50) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_messages(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        return result.scalar_one_or_none()


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def add(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        image_url: str | None = None,
        tokens: int = 0,
        extra: dict | None = None,
    ) -> Message:
        return await self.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            image_url=image_url,
            tokens=tokens,
            extra=extra or {},
        )

    async def recent_for_conversation(self, conversation_id: UUID, limit: int = 30) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        msgs = list(result.scalars().all())
        msgs.reverse()
        return msgs
