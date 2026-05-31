"""Retrieval-Augmented Generation pipeline.

Stages:
    1. embed user query
    2. vector retrieve from KB + chat memory
    3. re-rank + dedupe (by score, source)
    4. format into context block for the LLM
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import embed_text
from ai_engine.vector_store import VectorHit, search


@dataclass
class RAGDocument:
    id: str
    score: float
    text: str
    source: str
    metadata: dict[str, Any]


async def retrieve_context(
    query: str,
    *,
    user_id: str | None = None,
    top_k: int = 6,
    extra_collections: list[str] | None = None,
) -> list[RAGDocument]:
    """Retrieve and rank documents relevant to `query`."""
    embedding = await embed_text(query)
    docs: list[RAGDocument] = []

    # 1. Fashion knowledge base
    kb_hits = await search(settings.QDRANT_COLLECTION_KB, embedding, top_k=top_k)
    for h in kb_hits:
        docs.append(_to_doc(h, source="kb"))

    # 2. User's own chat memory
    if user_id:
        mem_hits = await search(
            settings.QDRANT_COLLECTION_CHATS,
            embedding,
            top_k=max(2, top_k // 2),
            filter_payload={"user_id": user_id},
        )
        for h in mem_hits:
            docs.append(_to_doc(h, source="memory"))

    # 3. Extra collections (optional)
    for collection in extra_collections or []:
        extra_hits = await search(collection, embedding, top_k=top_k)
        for h in extra_hits:
            docs.append(_to_doc(h, source=collection))

    # Re-rank: descending score, dedupe by id.
    seen: set[str] = set()
    ranked: list[RAGDocument] = []
    for d in sorted(docs, key=lambda x: x.score, reverse=True):
        if d.id in seen:
            continue
        seen.add(d.id)
        ranked.append(d)
        if len(ranked) >= top_k:
            break

    logger.debug(f"RAG retrieved {len(ranked)} documents for query of len {len(query)}")
    return ranked


def _to_doc(hit: VectorHit, source: str) -> RAGDocument:
    payload = hit.payload or {}
    text = (
        payload.get("text")
        or payload.get("content")
        or payload.get("summary")
        or payload.get("name")
        or ""
    )
    return RAGDocument(
        id=str(hit.id),
        score=hit.score,
        text=str(text),
        source=source,
        metadata={k: v for k, v in payload.items() if k not in {"text", "content", "summary"}},
    )


def format_kb_block(docs: list[RAGDocument], max_chars: int = 4000) -> str:
    """Format retrieved docs into a compact context block for prompts."""
    if not docs:
        return "(no relevant context)"
    lines: list[str] = []
    used = 0
    for d in docs:
        snippet = d.text.strip().replace("\n", " ")
        snippet = (snippet[:400] + "…") if len(snippet) > 400 else snippet
        line = f"[{d.source}#{d.id[:8]}] {snippet}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines)
