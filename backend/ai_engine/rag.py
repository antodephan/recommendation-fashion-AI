"""Retrieval-Augmented Generation pipeline.

Stages:
    1. embed user query
    2. optionally rewrite/expand the query for fashion-specific recall
    3. vector retrieve from KB + chat memory
    4. re-rank + dedupe (vector score + lexical/profile signals)
    5. format into context block for the LLM
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import embed_texts
from ai_engine.vector_store import VectorHit, search


@dataclass
class RAGDocument:
    id: str
    score: float
    text: str
    source: str
    metadata: dict[str, Any]


@dataclass
class RAGQueryExpansion:
    original: str
    search_queries: list[str]
    facets: dict[str, Any]


async def retrieve_context(
    query: str,
    *,
    user_id: str | None = None,
    top_k: int = 6,
    extra_collections: list[str] | None = None,
    user_profile: dict[str, Any] | None = None,
    enable_query_rewrite: bool | None = None,
) -> list[RAGDocument]:
    """Retrieve and rank documents relevant to `query`."""
    expansion = await expand_query(
        query,
        user_profile=user_profile,
        enabled=enable_query_rewrite,
    )
    embeddings = await embed_texts(expansion.search_queries)
    docs: list[RAGDocument] = []
    retrieval_k = max(top_k, top_k * max(1, settings.RAG_RETRIEVAL_MULTIPLIER))

    for search_query, embedding in zip(expansion.search_queries, embeddings):
        # 1. Fashion knowledge base
        kb_hits = await search(settings.QDRANT_COLLECTION_KB, embedding, top_k=retrieval_k)
        for h in kb_hits:
            docs.append(_to_doc(h, source="kb", matched_query=search_query))

        # 2. User's own chat memory
        if user_id:
            mem_hits = await search(
                settings.QDRANT_COLLECTION_CHATS,
                embedding,
                top_k=max(2, retrieval_k // 2),
                filter_payload={"user_id": user_id},
            )
            for h in mem_hits:
                docs.append(_to_doc(h, source="memory", matched_query=search_query))

        # 3. Extra collections (optional)
        for collection in extra_collections or []:
            extra_hits = await search(collection, embedding, top_k=retrieval_k)
            for h in extra_hits:
                docs.append(_to_doc(h, source=collection, matched_query=search_query))

    ranked = _dedupe_and_rank(
        docs,
        expansion=expansion,
        user_profile=user_profile,
        top_k=top_k,
    )

    logger.debug(
        "RAG retrieved "
        f"{len(ranked)} documents from {len(docs)} candidates "
        f"using {len(expansion.search_queries)} query variant(s)"
    )
    return ranked


async def expand_query(
    query: str,
    *,
    user_profile: dict[str, Any] | None = None,
    enabled: bool | None = None,
) -> RAGQueryExpansion:
    """Generate fashion-aware query variants for higher-recall retrieval."""
    fallback = _fallback_expansion(query)
    should_rewrite = settings.RAG_QUERY_REWRITE_ENABLED if enabled is None else enabled
    if not should_rewrite or not _openai_key_configured():
        return fallback

    try:
        # Import lazily to keep the RAG module usable in tests without initializing LLMs.
        from ai_engine.llm import LLMService

        profile_block = json.dumps(user_profile or {}, ensure_ascii=False)
        data = await LLMService().complete_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You rewrite fashion assistant queries for retrieval. "
                        "Return only JSON with keys: queries (array of 1-4 short search "
                        "queries) and facets (object with optional occasion, style, "
                        "colors, garment_types, season, gender, body_type). Keep the "
                        "user's intent unchanged. Include useful Vietnamese and English "
                        "fashion terms when helpful."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User query: {query}\n"
                        f"User profile JSON: {profile_block}\n"
                        "Rewrite for semantic retrieval over fashion knowledge and chat memory."
                    ),
                },
            ],
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning(f"RAG query rewrite skipped: {exc}")
        return fallback

    variants = [query]
    raw_queries = data.get("queries") if isinstance(data, dict) else None
    if isinstance(raw_queries, list):
        variants.extend(str(q) for q in raw_queries if str(q).strip())
    facets = data.get("facets") if isinstance(data, dict) and isinstance(data.get("facets"), dict) else {}

    return RAGQueryExpansion(
        original=query,
        search_queries=_unique_queries(variants),
        facets=facets,
    )


def _to_doc(hit: VectorHit, source: str, matched_query: str | None = None) -> RAGDocument:
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
        metadata={
            **{k: v for k, v in payload.items() if k not in {"text", "content", "summary"}},
            "vector_score": hit.score,
            **({"matched_query": matched_query} if matched_query else {}),
        },
    )


def _dedupe_and_rank(
    docs: list[RAGDocument],
    *,
    expansion: RAGQueryExpansion,
    user_profile: dict[str, Any] | None,
    top_k: int,
) -> list[RAGDocument]:
    """Dedupe by id and blend vector score with lexical/profile matches."""
    best_by_id: dict[str, RAGDocument] = {}
    for doc in docs:
        current = best_by_id.get(doc.id)
        if not current or doc.score > current.score:
            best_by_id[doc.id] = doc

    query_tokens = _tokens(
        " ".join(
            [
                expansion.original,
                " ".join(expansion.search_queries),
                _flatten_for_ranking(expansion.facets),
            ]
        )
    )
    profile_tokens = _tokens(_flatten_for_ranking(user_profile or {}))
    ranked: list[RAGDocument] = []

    for doc in best_by_id.values():
        doc_tokens = _tokens(f"{doc.text} {_flatten_for_ranking(doc.metadata)}")
        lexical = _overlap_score(query_tokens, doc_tokens)
        profile = _overlap_score(profile_tokens, doc_tokens) if profile_tokens else 0.0
        vector_score = float(doc.metadata.get("vector_score", doc.score) or 0.0)
        doc.score = (
            vector_score
            + settings.RAG_LEXICAL_RERANK_WEIGHT * lexical
            + settings.RAG_PROFILE_RERANK_WEIGHT * profile
        )
        doc.metadata["lexical_score"] = lexical
        if profile_tokens:
            doc.metadata["profile_score"] = profile
        ranked.append(doc)

    return sorted(ranked, key=lambda x: x.score, reverse=True)[:top_k]


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


def _fallback_expansion(query: str) -> RAGQueryExpansion:
    return RAGQueryExpansion(original=query, search_queries=_unique_queries([query]), facets={})


def _unique_queries(queries: list[str], max_queries: int = 4) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in queries:
        query = " ".join(str(raw).split())
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(query[:300])
        if len(result) >= max_queries:
            break
    return result or [""]


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[\w]+", text.lower()) if len(tok) > 1}


def _overlap_score(needles: set[str], haystack: set[str]) -> float:
    if not needles or not haystack:
        return 0.0
    return len(needles & haystack) / len(needles)


def _flatten_for_ranking(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten_for_ranking(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_for_ranking(v) for v in value)
    return str(value)


def _openai_key_configured() -> bool:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    return bool(api_key and api_key not in {"sk-missing", "sk-replace-me", "replace-me"})
