"""OpenAI embeddings wrapper with retry and batching."""

from __future__ import annotations

from typing import Sequence

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.logger import logger

_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY or "sk-missing")
    return _client


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
async def embed_texts(texts: Sequence[str], model: str | None = None) -> list[list[float]]:
    """Return embeddings for the given texts."""
    if not texts:
        return []
    client = get_openai()
    model = model or settings.OPENAI_EMBEDDING_MODEL
    try:
        resp = await client.embeddings.create(model=model, input=list(texts))
        return [item.embedding for item in resp.data]
    except Exception as exc:
        logger.exception(f"Embedding failure: {exc}")
        # Return zeros so downstream code keeps working — graceful degradation.
        return [[0.0] * settings.EMBEDDING_DIM for _ in texts]


async def embed_text(text: str, model: str | None = None) -> list[float]:
    vectors = await embed_texts([text], model=model)
    return vectors[0] if vectors else [0.0] * settings.EMBEDDING_DIM
