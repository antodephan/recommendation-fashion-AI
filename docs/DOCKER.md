# Docker Guide

## Stack

`docker-compose.yml` defines six services:

| Service   | Image / Build         | Ports        | Purpose                          |
|-----------|-----------------------|--------------|----------------------------------|
| postgres  | `postgres:16-alpine`  | 5432         | Relational data                  |
| redis     | `redis:7-alpine`      | 6379         | Cache + rate limit + streaming   |
| qdrant    | `qdrant/qdrant`       | 6333, 6334   | Vector database                  |
| backend   | `./backend/Dockerfile`| 8000         | FastAPI app + AI engine          |
| frontend  | `./frontend/Dockerfile`| 3000        | Next.js 14 app                   |
| nginx     | `./nginx/Dockerfile`  | 80, 443      | Reverse proxy + rate limits      |

## Volumes

| Volume         | Mount                      | Contents                |
|----------------|----------------------------|-------------------------|
| postgres_data  | `/var/lib/postgresql/data` | Postgres database files |
| redis_data     | `/data`                    | Redis AOF persistence   |
| qdrant_data    | `/qdrant/storage`          | Vector index data       |
| uploads_data   | `/app/uploads`             | User-uploaded images    |

## Healthchecks

- Postgres: `pg_isready`
- Redis: `redis-cli ping`
- Backend: `GET /health`

## Production tips

- Set `COOKIE_SECURE=true` and configure HTTPS via Nginx (Let's Encrypt + cert-manager).
- Increase Uvicorn workers: set `command:` accordingly or use Gunicorn + UvicornWorker.
- Externalize Postgres / Redis / Qdrant to managed services (RDS, ElastiCache, Qdrant Cloud).
- Mount logs to a persistent volume or stream to Loki / CloudWatch.
- Enable Sentry by setting `SENTRY_DSN`.
- Lock down Qdrant with `QDRANT_API_KEY` and put it on a private network.

## CI/CD outline

Suggested pipeline (GitHub Actions):

1. Lint + test backend (`ruff`, `pytest`)
2. Lint + build frontend (`next build`)
3. Build & push Docker images (backend / frontend / nginx)
4. Deploy via `docker compose -f compose.prod.yml up -d` on the target host
   (or push to Kubernetes via Helm)
