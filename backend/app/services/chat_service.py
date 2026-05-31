"""Chat orchestration: history, RAG, streaming, memory storage."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logger import logger
from app.models.chat import Conversation, MessageRole
from app.models.user import User
from app.repositories.chat_repo import ConversationRepository, MessageRepository
from app.schemas.outfit import RecommendationRequest
from app.services.analytics_service import AnalyticsService
from app.services.outfit_intent import needs_outfit_recommendation
from app.services.preference_service import PreferenceService
from app.services.recommendation_service import RecommendationService

from ai_engine.embeddings import embed_text
from ai_engine.llm import LLMService
from ai_engine.prompts import SYSTEM_PROMPT, language_instruction
from ai_engine.rag import format_kb_block, retrieve_context
from ai_engine.vector_store import upsert_points
from ai_engine.vision import resolve_image_url_for_llm
from app.config import settings


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.llm = LLMService()
        self.analytics = AnalyticsService(db)
        self.preferences = PreferenceService(db)
        self.recommendations = RecommendationService(db)

    async def list_conversations(self, user: User) -> list[Conversation]:
        return await self.conversations.list_for_user(user.id)

    async def get_conversation(self, user: User, conversation_id: UUID) -> Conversation:
        convo = await self.conversations.get_with_messages(conversation_id, user.id)
        if not convo:
            raise NotFoundError("Conversation not found")
        return convo

    async def create_conversation(self, user: User, title: str | None) -> Conversation:
        return await self.conversations.create(user_id=user.id, title=title or "New conversation")

    async def delete_conversation(self, user: User, conversation_id: UUID) -> None:
        convo = await self.conversations.get_with_messages(conversation_id, user.id)
        if not convo:
            raise NotFoundError("Conversation not found")
        await self.conversations.delete(conversation_id)

    async def rename_conversation(self, user: User, conversation_id: UUID, title: str) -> Conversation:
        convo = await self.conversations.get_with_messages(conversation_id, user.id)
        if not convo:
            raise NotFoundError("Conversation not found")
        convo.title = title
        await self.db.commit()
        return convo

    async def _resolve_conversation(self, user: User, conversation_id: UUID | None) -> Conversation:
        if conversation_id:
            convo = await self.conversations.get_with_messages(conversation_id, user.id)
            if not convo:
                raise NotFoundError("Conversation not found")
            return convo
        return await self.conversations.create(user_id=user.id, title="New conversation")

    async def _build_prompt(
        self, user: User, convo: Conversation, content: str, image_url: str | None
    ) -> list[dict[str, Any]]:
        history = await self.messages.recent_for_conversation(convo.id, limit=20)
        kb_docs = await retrieve_context(content, user_id=str(user.id), top_k=4)
        kb_block = format_kb_block(kb_docs)

        sys_msg = SYSTEM_PROMPT + language_instruction(user.locale)
        if kb_block and kb_block != "(no relevant context)":
            sys_msg += f"\n\n## Retrieved knowledge\n{kb_block}"
        if user.preferences or user.gender or user.body_type:
            prefs = user.preferences or {}
            sys_msg += (
                f"\n\n## User profile\n"
                f"- Gender: {user.gender or 'unspecified'}\n"
                f"- Body type: {user.body_type or 'unspecified'}\n"
                f"- Location: {user.location or 'unspecified'}\n"
                f"- Favorite colors: {', '.join(prefs.get('colors', [])) or '—'}\n"
                f"- Preferred brands: {', '.join(prefs.get('brands', [])) or '—'}\n"
                f"- Preferred styles: {', '.join(prefs.get('styles', [])) or '—'}\n"
                f"- Budget: {prefs.get('budget') or '—'}\n"
            )

        messages: list[dict[str, Any]] = [{"role": "system", "content": sys_msg}]
        for m in history:
            if m.role == MessageRole.SYSTEM:
                continue
            messages.append({"role": m.role.value, "content": m.content})

        if image_url:
            llm_image_url = image_url
            try:
                llm_image_url = resolve_image_url_for_llm(image_url)
            except Exception as exc:
                logger.warning(f"Image URL not usable for LLM, text-only: {exc}")
                content = (
                    f"{content}\n\n"
                    "(User attached an inspiration image, but it could not be loaded for analysis.)"
                ).strip()
            else:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": content},
                            {"type": "image_url", "image_url": {"url": llm_image_url}},
                        ],
                    }
                )
                return messages
        messages.append({"role": "user", "content": content})
        return messages

    async def _post_turn_hooks(
        self,
        user: User,
        convo: Conversation,
        content: str,
        reply: str,
        image_url: str | None,
    ) -> dict[str, Any] | None:
        try:
            await self._index_memory(user, convo, content, reply)
            await self.preferences.learn_from_exchange(user, content, reply)
            await self.analytics.log_event(user.id, "chat_message", {"convo": str(convo.id), "len": len(reply)})

            if not needs_outfit_recommendation(content, has_image=bool(image_url)):
                return None
            rec = await self.recommendations.recommend(
                user,
                RecommendationRequest(
                    query=content,
                    conversation_id=convo.id,
                    use_weather=True,
                    image_url=image_url,
                ),
            )
            return {
                "reasoning": rec.reasoning,
                "confidence": rec.confidence,
                "items": [item.model_dump(mode="json") for item in rec.items],
            }
        except Exception as exc:
            logger.warning(f"Post-turn chat hooks failed (non-fatal): {exc}")
            return None

    async def send_message(
        self,
        user: User,
        content: str,
        conversation_id: UUID | None = None,
        image_url: str | None = None,
    ) -> dict[str, Any]:
        convo = await self._resolve_conversation(user, conversation_id)
        await self.messages.add(
            conversation_id=convo.id,
            role=MessageRole.USER,
            content=content,
            image_url=image_url,
        )
        prompt = await self._build_prompt(user, convo, content, image_url)
        started = time.perf_counter()
        reply = await self.llm.complete(prompt)
        latency_ms = (time.perf_counter() - started) * 1000

        rec_payload = await self._post_turn_hooks(user, convo, content, reply, image_url)
        extra: dict[str, Any] = {"latency_ms": latency_ms, "model": self.llm.model}
        if rec_payload:
            extra["recommendations"] = rec_payload

        assistant_msg = await self.messages.add(
            conversation_id=convo.id,
            role=MessageRole.ASSISTANT,
            content=reply,
            extra=extra,
        )

        result: dict[str, Any] = {
            "conversation_id": str(convo.id),
            "id": str(assistant_msg.id),
            "role": "assistant",
            "content": reply,
            "created_at": assistant_msg.created_at.isoformat(),
        }
        if rec_payload:
            result["recommendations"] = rec_payload
        return result

    async def stream_message(
        self,
        user: User,
        content: str,
        conversation_id: UUID | None = None,
        image_url: str | None = None,
    ) -> AsyncIterator[str]:
        convo = await self._resolve_conversation(user, conversation_id)
        await self.messages.add(
            conversation_id=convo.id,
            role=MessageRole.USER,
            content=content,
            image_url=image_url,
        )
        yield self._sse("meta", {"conversation_id": str(convo.id)})

        prompt = await self._build_prompt(user, convo, content, image_url)
        buffer: list[str] = []
        started = time.perf_counter()

        async for token in self.llm.stream(prompt):
            buffer.append(token)
            yield self._sse("delta", {"content": token})

        reply = "".join(buffer)
        latency_ms = (time.perf_counter() - started) * 1000

        rec_payload = await self._post_turn_hooks(user, convo, content, reply, image_url)
        extra: dict[str, Any] = {"latency_ms": latency_ms, "model": self.llm.model}
        if rec_payload:
            extra["recommendations"] = rec_payload

        assistant_msg = await self.messages.add(
            conversation_id=convo.id,
            role=MessageRole.ASSISTANT,
            content=reply,
            extra=extra,
        )

        yield self._sse(
            "done",
            {
                "id": str(assistant_msg.id),
                "conversation_id": str(convo.id),
                "content": reply,
                "latency_ms": latency_ms,
            },
        )
        if rec_payload:
            yield self._sse("recommendations", rec_payload)

    @staticmethod
    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def _index_memory(
        self, user: User, convo: Conversation, user_msg: str, assistant_msg: str
    ) -> None:
        try:
            text = f"User: {user_msg}\nAssistant: {assistant_msg}"
            vector = await embed_text(text)
            await upsert_points(
                settings.QDRANT_COLLECTION_CHATS,
                [(
                    str(convo.id),
                    vector,
                    {
                        "user_id": str(user.id),
                        "conversation_id": str(convo.id),
                        "text": text[:2000],
                    },
                )],
            )
        except Exception as exc:
            logger.warning(f"Chat memory indexing failed: {exc}")
