# AI Fashion Recommendation System

A production-ready, full-stack AI fashion assistant that delivers personalized
outfit recommendations through a ChatGPT-style conversational interface,
powered by RAG over fashion knowledge, vector search over user/outfit
embeddings, and multimodal understanding of clothing images.

> Built for portfolio presentation, startup MVPs, and real-world deployment.

---

## Features

- ChatGPT-style streaming chat (SSE + WebSockets)
- Multimodal: chat with images (CLIP / BLIP embeddings)
- Personalized recommendations from user embeddings + collaborative + trend signals
- RAG over fashion knowledge base (Qdrant + LangChain)
- Weather, season, body type and budget aware suggestions
- Modern Next.js 14 + Tailwind + ShadCN UI + Framer Motion frontend
- Secure JWT auth with refresh tokens, OAuth (Google/Facebook), email verification
- Role-Based Access Control (User / Admin / Super Admin)
- Redis caching, rate limiting, streaming state
- Admin dashboard with usage analytics, prompts, errors, system health
- Loguru structured logging + optional Sentry
- Dockerized: frontend, backend, postgres, redis, qdrant, nginx
- Production-ready: clean architecture, async APIs, OpenAPI docs, healthchecks

## Tech Stack

| Layer       | Technology                                                |
|-------------|------------------------------------------------------------|
| Frontend    | Next.js 14, TypeScript, TailwindCSS, ShadCN UI, Framer Motion |
| Backend     | FastAPI (Python 3.11), SQLAlchemy 2 (async), Pydantic v2  |
| AI / LLM    | OpenAI `gpt-5.4-mini`, OpenAI Embeddings, vision API       |
| RAG         | LangChain                                                  |
| Vector DB   | Qdrant                                                     |
| Database    | PostgreSQL 16                                              |
| Cache / Queue | Redis 7                                                   |
| Reverse Proxy | Nginx                                                    |
| Logging     | Loguru, optional Sentry                                    |
| Deploy      | Docker + docker compose                                    |

## Repository Layout

```
.
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/                  # FastAPI + AI engine
│   ├── app/                  # API, services, models, schemas, middleware
│   ├── ai_engine/            # LLM, RAG, recommendation, vision
│   ├── alembic/              # DB migrations
│   ├── tests/
│   └── Dockerfile
├── frontend/                 # Next.js 14 app
│   ├── src/
│   │   ├── app/              # App-router pages
│   │   ├── components/       # UI building blocks
│   │   ├── lib/              # API client, utils, auth
│   │   └── store/            # Zustand stores
│   └── Dockerfile
├── nginx/                    # Reverse proxy configuration
├── scripts/                  # Seed data and utilities
└── docs/                     # Architecture, API, Setup, Docker, ENV guides
```

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# fill in OPENAI_API_KEY, JWT_SECRET, OAuth keys, etc.

# 2. Build & launch the stack
docker compose up --build

# 3. Open the app
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000/docs (Swagger)
# Qdrant:    http://localhost:6333/dashboard
```

See [`docs/SETUP.md`](docs/SETUP.md) for the full development guide.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Setup Guide](docs/SETUP.md)
- [Docker Guide](docs/DOCKER.md)
- [Environment Variables](docs/ENV.md)

## License

MIT — designed for portfolio, MVPs, and production deployment.
