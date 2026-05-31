# Environment Variables

All variables are loaded from `.env` (see `.env.example`).

## General

| Variable          | Default                       | Description                       |
|-------------------|-------------------------------|-----------------------------------|
| ENVIRONMENT       | `development`                 | development / staging / production|
| LOG_LEVEL         | `INFO`                        | DEBUG / INFO / WARNING / ERROR    |
| BACKEND_CORS_ORIGINS | `http://localhost:3000,…`  | Comma separated allowed origins   |

## Security

| Variable                       | Default                | Description                       |
|--------------------------------|------------------------|-----------------------------------|
| JWT_SECRET                     | _required_             | HS256 signing key (≥32 chars)     |
| JWT_ALGORITHM                  | `HS256`                |                                   |
| ACCESS_TOKEN_EXPIRE_MINUTES    | `30`                   |                                   |
| REFRESH_TOKEN_EXPIRE_DAYS      | `14`                   |                                   |
| COOKIE_DOMAIN                  | `localhost`            | Cookie scope                       |
| COOKIE_SECURE                  | `false`                | `true` in HTTPS production         |

## Database / Cache / Vector

| Variable     | Default                                                       |
|--------------|---------------------------------------------------------------|
| DATABASE_URL | `postgresql+asyncpg://fashion:fashion@postgres:5432/fashion`  |
| REDIS_URL    | `redis://redis:6379/0`                                        |
| QDRANT_HOST  | `qdrant`                                                      |
| QDRANT_PORT  | `6333`                                                        |
| QDRANT_API_KEY | _(optional)_                                                |

## OpenAI

| Variable                | Description                          |
|-------------------------|--------------------------------------|
| OPENAI_API_KEY          | _required_                            |
| OPENAI_CHAT_MODEL       | `gpt-5.4-mini` (or any chat model)    |
| OPENAI_EMBEDDING_MODEL  | `text-embedding-3-small`              |
| OPENAI_VISION_MODEL     | model with image input                |

## OAuth

| Variable                  | Description              |
|---------------------------|--------------------------|
| GOOGLE_CLIENT_ID/SECRET   | Google OAuth credentials |
| GOOGLE_REDIRECT_URI       | Callback URL             |
| FACEBOOK_CLIENT_ID/SECRET | Facebook credentials     |
| FACEBOOK_REDIRECT_URI     | Callback URL             |

## Email (SMTP)

| Variable     | Description                                |
|--------------|--------------------------------------------|
| SMTP_HOST    | If empty, email is logged to stdout (dev)  |
| SMTP_PORT    | Usually 587                                |
| SMTP_USERNAME / SMTP_PASSWORD | Credentials               |
| SMTP_FROM_EMAIL / SMTP_FROM_NAME | "From" header           |

## Weather

| Variable           | Description                                  |
|--------------------|----------------------------------------------|
| OPENWEATHER_API_KEY| If empty, a stub forecast is returned        |

## Sentry

| Variable                  | Description           |
|---------------------------|-----------------------|
| SENTRY_DSN                | If set, enables Sentry|
| SENTRY_TRACES_SAMPLE_RATE | `0.1` default          |

## Bootstrap

| Variable             | Description                          |
|----------------------|--------------------------------------|
| SUPERADMIN_EMAIL     | Super admin created at first boot    |
| SUPERADMIN_PASSWORD  | Super admin password                 |

## RapidAPI H&M

| Variable                     | Default                                              | Description                          |
|------------------------------|------------------------------------------------------|--------------------------------------|
| RAPIDAPI_KEY                 | _(required for H&M catalog)_                         | RapidAPI key                         |
| RAPIDAPI_HM_HOST             | `apidojo-hm-hennes-mauritz-v1.p.rapidapi.com`        | API host header                      |
| HM_REGION                    | `vn`                                                 | Preferred region (auto-resolved)     |
| HM_CATALOG_IMPORT_LIMIT      | `2000`                                               | Max products per import              |
| HM_CATALOG_AUTO_IMPORT       | `true`                                               | Run import on bootstrap              |
| HM_TRENDS_SYNC_INTERVAL_HOURS| `72`                                                 | Scheduled trends sync interval       |
| HM_SCHEDULER_ENABLED         | `true`                                               | Background APScheduler jobs          |
| CATALOG_AUTO_IMPORT          | `false`                                              | Legacy CSV import (off when using H&M) |
