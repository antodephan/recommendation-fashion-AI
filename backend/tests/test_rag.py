"""Unit tests for RAG ranking helpers."""

from ai_engine.rag import RAGDocument, RAGQueryExpansion, _dedupe_and_rank, _unique_queries


def test_unique_queries_preserves_order_and_removes_duplicates():
    assert _unique_queries([" blazer  outfit ", "Blazer outfit", "", "office style"]) == [
        "blazer outfit",
        "office style",
    ]


def test_dedupe_and_rank_blends_lexical_and_profile_signals():
    expansion = RAGQueryExpansion(
        original="office interview outfit",
        search_queries=["office interview outfit", "professional blazer outfit"],
        facets={"occasion": "interview", "style": "office"},
    )
    docs = [
        RAGDocument(
            id="generic",
            score=0.70,
            text="Leather boots for weekend streetwear.",
            source="kb",
            metadata={"vector_score": 0.70},
        ),
        RAGDocument(
            id="specific",
            score=0.60,
            text="A black blazer works well for office interviews and petite body types.",
            source="kb",
            metadata={"vector_score": 0.60},
        ),
    ]

    ranked = _dedupe_and_rank(
        docs,
        expansion=expansion,
        user_profile={"body_type": "petite", "styles": ["office"]},
        top_k=1,
    )

    assert [doc.id for doc in ranked] == ["specific"]
    assert ranked[0].metadata["lexical_score"] > 0
    assert ranked[0].metadata["profile_score"] > 0


def test_dedupe_and_rank_keeps_best_vector_duplicate():
    expansion = RAGQueryExpansion(
        original="summer dress",
        search_queries=["summer dress"],
        facets={},
    )
    docs = [
        RAGDocument(
            id="same",
            score=0.40,
            text="Summer dress guide.",
            source="kb",
            metadata={"vector_score": 0.40, "matched_query": "summer dress"},
        ),
        RAGDocument(
            id="same",
            score=0.90,
            text="Summer dress guide.",
            source="kb",
            metadata={"vector_score": 0.90, "matched_query": "light summer dress"},
        ),
    ]

    ranked = _dedupe_and_rank(docs, expansion=expansion, user_profile=None, top_k=1)

    assert len(ranked) == 1
    assert ranked[0].id == "same"
    assert ranked[0].metadata["vector_score"] == 0.90
