"""WebSocket endpoint for real-time chat streaming + notifications."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.security import decode_token
from app.database import AsyncSessionLocal
from app.repositories.user_repo import UserRepository
from app.services.chat_service import ChatService

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    """
    Bidirectional chat. Client sends:
        {"type":"message","content":"...","conversation_id":"<uuid?>","image_url":"<?>"}
    Server replies with streaming events:
        {"type":"meta", ...}
        {"type":"delta","content":"..."}
        {"type":"done", ...}
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token, expected_type="access")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = UUID(payload["sub"])
    await websocket.accept()

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        user_repo = UserRepository(db)
        user = await user_repo.get(user_id)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        service = ChatService(db)
        logger.info(f"WS connected: user={user.email}")

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "invalid json"})
                    continue

                if msg.get("type") != "message":
                    await websocket.send_json({"type": "error", "message": "unknown type"})
                    continue

                content = (msg.get("content") or "").strip()
                if not content:
                    await websocket.send_json({"type": "error", "message": "empty content"})
                    continue

                conversation_id = msg.get("conversation_id")
                image_url = msg.get("image_url")

                async for sse_chunk in service.stream_message(
                    user, content,
                    UUID(conversation_id) if conversation_id else None,
                    image_url,
                ):
                    # convert SSE format to JSON frames
                    for block in sse_chunk.split("\n\n"):
                        if not block.strip():
                            continue
                        ev_line, data_line = "", ""
                        for line in block.split("\n"):
                            if line.startswith("event:"):
                                ev_line = line[len("event:"):].strip()
                            elif line.startswith("data:"):
                                data_line = line[len("data:"):].strip()
                        if not ev_line:
                            continue
                        await websocket.send_json({"type": ev_line, **json.loads(data_line or "{}")})

        except WebSocketDisconnect:
            logger.info(f"WS disconnected: user={user.email}")
        except Exception as exc:
            logger.exception(f"WS error: {exc}")
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
