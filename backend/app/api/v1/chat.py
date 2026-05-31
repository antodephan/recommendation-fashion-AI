"""Chat endpoints: streaming + REST."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limit
from app.schemas.chat import ConversationRead, MessageCreate, MessageRead
from app.schemas.common import Message
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(user: CurrentUser, db: DbSession):
    service = ChatService(db)
    return await service.list_conversations(user)


@router.post("/conversations", response_model=ConversationRead)
async def create_conversation(user: CurrentUser, db: DbSession, title: str | None = None):
    service = ChatService(db)
    return await service.create_conversation(user, title)


@router.get("/conversations/{conversation_id}", response_model=list[MessageRead])
async def get_conversation(conversation_id: UUID, user: CurrentUser, db: DbSession):
    service = ChatService(db)
    convo = await service.get_conversation(user, conversation_id)
    return convo.messages


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def rename_conversation(conversation_id: UUID, title: str, user: CurrentUser, db: DbSession):
    service = ChatService(db)
    return await service.rename_conversation(user, conversation_id, title)


@router.delete("/conversations/{conversation_id}", response_model=Message)
async def delete_conversation(conversation_id: UUID, user: CurrentUser, db: DbSession):
    service = ChatService(db)
    await service.delete_conversation(user, conversation_id)
    return Message(message="deleted")


@router.post(
    "/send",
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_CHAT, scope="chat"))],
)
async def send(payload: MessageCreate, user: CurrentUser, db: DbSession):
    service = ChatService(db)
    return await service.send_message(
        user, payload.content, payload.conversation_id, payload.image_url
    )


@router.post(
    "/stream",
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_CHAT, scope="chat-stream"))],
)
async def stream(payload: MessageCreate, user: CurrentUser):
    """SSE stream — use a dedicated DB session for the full generator lifetime."""
    user_id = user.id

    async def generate():
        from app.core.exceptions import NotFoundError
        from app.core.logger import logger
        from app.database import AsyncSessionLocal
        from app.repositories.user_repo import UserRepository

        async with AsyncSessionLocal() as db:
            stream_user = await UserRepository(db).get(user_id)
            if not stream_user:
                yield ChatService._sse("error", {"message": "User not found"})
                return
            service = ChatService(db)
            try:
                async for chunk in service.stream_message(
                    stream_user,
                    payload.content,
                    payload.conversation_id,
                    payload.image_url,
                ):
                    yield chunk
            except NotFoundError as exc:
                yield ChatService._sse("error", {"message": str(exc)})
            except Exception as exc:
                logger.exception(f"Chat stream failed: {exc}")
                yield ChatService._sse("error", {"message": "Chat stream failed"})

    return StreamingResponse(generate(), media_type="text/event-stream")
