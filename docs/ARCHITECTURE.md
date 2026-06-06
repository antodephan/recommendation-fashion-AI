# Architecture

Couture AI is composed of three independently deployable services + three
infrastructure components, behind an Nginx reverse proxy.

```
                         ┌────────────────┐
                         │     Nginx      │   :80 / :443
                         └──────┬─────────┘
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
      ┌────────────┐     ┌────────────┐    ┌────────────┐
      │  Next.js   │     │  FastAPI   │    │  Static    │
      │ (frontend) │     │ (backend)  │    │ (uploads)  │
      └────────────┘     └─────┬──────┘    └────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
   ┌─────────┐           ┌──────────┐            ┌──────────┐
   │ Postgres│           │  Redis   │            │  Qdrant  │
   │ (truth) │           │ (cache,  │            │ (vector) │
   │         │           │  rate    │            │          │
   │         │           │  limits) │            │          │
   └─────────┘           └──────────┘            └──────────┘
```

## Layered Backend

```
backend/
├── app/
│   ├── api/           # HTTP + WS layer (FastAPI routers)
│   ├── services/      # Business orchestration (use cases)
│   ├── repositories/  # Data access (async SQLAlchemy)
│   ├── models/        # ORM entities
│   ├── schemas/       # Pydantic v2 contracts
│   ├── core/          # Security, logging, deps, exceptions, cache, rate-limit
│   ├── middleware/    # ASGI middleware (correlation id, security headers)
│   ├── scripts/       # Bootstrap + seed
│   └── main.py        # FastAPI factory
└── ai_engine/
    ├── llm.py         # OpenAI chat + streaming
    ├── embeddings.py  # OpenAI embeddings
    ├── vector_store.py# Qdrant async client
    ├── rag.py         # RAG pipeline
    ├── recommender.py # Hybrid recommendation engine
    ├── vision.py      # Multimodal image understanding
    └── prompts.py     # System + recommendation prompts
```

## Recommendation Pipeline

```
 user_query ──┐
              ▼
        embed_query  ───►  Qdrant.search(outfits) ─┐
              │                                    │
        DB content filter (SQL) ──────────────────►│
              │                                    │
        Collaborative signals (favorites graph) ──►│
                                                   ▼
                                            merge + weight
                                                   │
                                                   ▼
                                       LLM re-ranking + reasoning
                                                   │
                                                   ▼
                               RecommendationResponse persisted
                                  to Postgres + analytics event
```

## RAG Pipeline

```
 user_query → optional LLM query rewrite/expansion
        → embed query variants
        → Qdrant.kb.search(top_k × recall multiplier)
                    + Qdrant.chat_memory.search(user_filter)
        → de-dupe + vector/lexical/profile re-rank
        → format context block (≤ 4000 chars)
        → inject into system prompt
        → LLM completion / stream
```

Query rewriting is controlled by `RAG_QUERY_REWRITE_ENABLED`; if the OpenAI key is not
configured or rewriting fails, retrieval falls back to the original query.

## Vector Collections

| Collection         | Purpose                                       | Vector source         |
|--------------------|-----------------------------------------------|------------------------|
| `outfits`          | Outfit catalog for similarity search          | text representation   |
| `products`         | Reserved for future product ingest            | text representation   |
| `user_profiles`    | Aggregated user taste vector                  | preferences + history |
| `chat_memory`      | Per-user conversational memory                | user+assistant turns  |
| `fashion_kb`       | RAG knowledge base                            | curated docs          |

## Security Model

- JWT access (30m) + refresh (14d) with rotation + revoke list (`refresh_tokens` table)
- Bcrypt password hashes
- HttpOnly + SameSite cookies for browser sessions
- Per-IP Redis-backed sliding window rate limits (auth / chat / global)
- Centralized exception handler emits structured error payloads
- Security headers via middleware (CSP-ready, X-Frame-Options, HSTS)
- Email verification + password-reset via one-time SHA-256 hashed codes
- RBAC checked through FastAPI dependencies (`require_admin`, `require_superadmin`)

## Observability

- Loguru structured logs with rotation
- Correlation IDs threaded through every request
- API usage written to `api_usage` for billing/quota
- Event log table for product analytics
- Optional Sentry integration for production
