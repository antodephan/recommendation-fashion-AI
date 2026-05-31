"""Learn user preferences from chat and index profile vectors."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import logger
from app.models.user import User
from app.services.analytics_service import AnalyticsService

from ai_engine.embeddings import embed_text
from ai_engine.llm import LLMService
from ai_engine.vector_store import upsert_points


def _deep_merge_prefs(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    for key, val in incoming.items():
        if val is None:
            continue
        if key in ("colors", "styles", "brands", "occasions", "avoid") and isinstance(val, list):
            old = merged.get(key) or []
            combined = list(dict.fromkeys([*(old if isinstance(old, list) else []), *val]))
            merged[key] = combined[:20]
        elif key == "budget" and val:
            merged[key] = val
        elif val:
            merged[key] = val
    return merged


def profile_to_text(user: User) -> str:
    prefs = user.preferences or {}
    parts = [
        f"gender: {user.gender}" if user.gender else "",
        f"body_type: {user.body_type}" if user.body_type else "",
        f"location: {user.location}" if user.location else "",
        f"colors: {', '.join(prefs.get('colors', []))}",
        f"styles: {', '.join(prefs.get('styles', []))}",
        f"brands: {', '.join(prefs.get('brands', []))}",
        f"occasions: {', '.join(prefs.get('occasions', []))}",
        f"budget: {prefs.get('budget')}" if prefs.get("budget") else "",
        f"avoid: {', '.join(prefs.get('avoid', []))}",
    ]
    return ". ".join(p for p in parts if p and p.split(": ", 1)[-1])


class PreferenceService:
    def __init__(self, db: AsyncSession, llm: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm or LLMService()
        self.analytics = AnalyticsService(db)

    async def learn_from_exchange(
        self, user: User, user_msg: str, assistant_msg: str
    ) -> dict[str, Any] | None:
        """Extract preferences from a chat turn, merge, embed profile vector."""
        prompt = [
            {
                "role": "system",
                "content": (
                    "Extract fashion preference signals from the user message. "
                    "Return JSON only: "
                    '{"colors":[],"styles":[],"brands":[],"occasions":[],"avoid":[],"budget":null}. '
                    "Use empty arrays when unknown."
                ),
            },
            {
                "role": "user",
                "content": f"User said:\n{user_msg}\n\nAssistant replied:\n{assistant_msg[:800]}",
            },
        ]
        try:
            data = await self.llm.complete_json(prompt, temperature=0.2)
        except Exception as exc:
            logger.warning(f"Preference extraction failed: {exc}")
            return None

        if not any(data.get(k) for k in ("colors", "styles", "brands", "occasions", "budget", "avoid")):
            return None

        user.preferences = _deep_merge_prefs(user.preferences or {}, data)
        await self.db.commit()
        await self._index_profile_vector(user)
        await self.analytics.log_event(
            user.id,
            "preference_updated",
            {
                "colors": data.get("colors", []),
                "styles": data.get("styles", []),
                "brands": data.get("brands", []),
            },
        )
        return data

    async def refresh_profile_vector(self, user: User) -> None:
        await self._index_profile_vector(user)

    async def _index_profile_vector(self, user: User) -> None:
        try:
            text = profile_to_text(user)
            if not text.strip():
                return
            vector = await embed_text(text)
            await upsert_points(
                settings.QDRANT_COLLECTION_USERS,
                [
                    (
                        str(user.id),
                        vector,
                        {
                            "user_id": str(user.id),
                            "text": text[:2000],
                            "location": user.location,
                        },
                    )
                ],
            )
        except Exception as exc:
            logger.warning(f"User profile vector indexing failed: {exc}")
