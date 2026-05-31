# Setup Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Node 20+ (for local frontend development only)
- Python 3.11+ (for local backend development only)
- An OpenAI API key (`OPENAI_API_KEY`)

Optional:

- Google OAuth client (for Google sign-in)
- Facebook OAuth client
- OpenWeather API key (for weather-aware recommendations)

## 1. Configure environment

```bash
cp .env.example .env
```

At minimum fill in:

- `OPENAI_API_KEY`
- `JWT_SECRET` (rotate to a 32+ char random string)
- `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD`
- `RAPIDAPI_KEY` (H&M catalog + trends via RapidAPI)

Optional H&M settings in `.env`:

- `HM_REGION=vn` — resolved via `regions/list` at runtime
- `HM_CATALOG_AUTO_IMPORT=true` — import on bootstrap
- `CATALOG_AUTO_IMPORT=false` — legacy CSV disabled by default

## 2. Run with Docker Compose

```bash
docker compose up --build
```

This boots:

- Postgres (5432), Redis (6379), Qdrant (6333)
- Backend on http://localhost:8000 (Swagger at `/docs`)
- Frontend on http://localhost:3000
- Nginx on http://localhost (port 80)

The first start runs `alembic upgrade head`, then bootstraps a super-admin
user, seeds demo outfits, **imports the H&M catalog via RapidAPI** (when
`RAPIDAPI_KEY` is set), syncs H&M trends, and the RAG knowledge base.

Legacy CSV import runs only when `CATALOG_AUTO_IMPORT=true` and H&M auto-import is off.

## 3. Sign in as super admin

Open http://localhost:3000/login and use:

- email: `admin@couture.ai`
- password: `changeme123!`

Visit `/admin` and `/analytics` (admin-only routes).

## 4. Local development without Docker

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://fashion:fashion@localhost:5432/fashion
export REDIS_URL=redis://localhost:6379/0
export QDRANT_HOST=localhost
alembic upgrade head
python -m app.scripts.bootstrap
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 5. Tests

```bash
cd backend
pytest -q
```

## 6. Common tasks

| Task                                  | Command                                                    |
|---------------------------------------|------------------------------------------------------------|
| Rebuild backend only                  | `docker compose up --build backend`                        |
| Generate new migration                | `docker compose run backend alembic revision -m "msg" --autogenerate` |
| Re-seed outfits + KB                  | `docker compose run backend python -m app.scripts.bootstrap`|
| Import H&M catalog                    | `docker compose exec backend python -m app.scripts.import_hm_catalog` |
| Sync H&M trends                       | `docker compose exec backend python -m app.scripts.sync_hm_trends` |
| Admin: trigger sync                   | `POST /api/v1/admin/hm/sync-catalog` or `/hm/sync-trends` |
| Tail logs                             | `docker compose logs -f backend`                           |
| Reset all data                        | `docker compose down -v`                                   |
