"""LLM service: streaming + structured completions."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import get_openai

_FALLBACK_MSG = "I'm having trouble reaching the AI service right now. Please try again."


def _chat_kwargs(
    *,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int | None,
    response_format: dict | None,
    stream: bool = False,
) -> dict[str, Any]:
    """Build OpenAI chat completion kwargs; omit None (gpt-5.x rejects null max_tokens)."""
    kwargs: dict[str, Any] = {
        "model": settings.OPENAI_CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if response_format is not None:
        kwargs["response_format"] = response_format
    if stream:
        kwargs["stream"] = True
    return kwargs


class LLMService:
    """High-level LLM helper used by chat + recommendation services."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self.client = client or get_openai()
        self.model = settings.OPENAI_CHAT_MODEL

    @retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(2), reraise=True)
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        try:
            resp = await self.client.chat.completions.create(
                **_chat_kwargs(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            )
        except Exception as exc:
            logger.exception(f"LLM completion failed: {exc}")
            return _FALLBACK_MSG
        return resp.choices[0].message.content or ""

    async def complete_json(
        self, messages: list[dict[str, Any]], temperature: float = 0.4
    ) -> dict[str, Any]:
        raw = await self.complete(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        if raw == _FALLBACK_MSG:
            return {"reasoning": raw, "items": []}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON; attempting recovery")
            try:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                return json.loads(raw[start:end])
            except Exception:
                return {"reasoning": raw, "items": []}

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Async generator yielding partial content tokens."""
        try:
            stream = await self.client.chat.completions.create(
                **_chat_kwargs(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=None,
                    stream=True,
                )
            )
        except Exception as exc:
            logger.exception(f"LLM stream failed: {exc}")
            yield _FALLBACK_MSG
            return

        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (IndexError, AttributeError):
                delta = None
            if delta:
                yield delta
