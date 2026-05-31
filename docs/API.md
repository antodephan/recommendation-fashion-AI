# API Reference

Base URL: `http://localhost:8000/api/v1` (or via Nginx at `/api/v1`).
Interactive docs: `/docs` (Swagger UI), `/redoc`.

All responses follow:

```json
{ ... resource ... }
```

or, on error:

```json
{ "error": { "code": "<machine_code>", "message": "<human>", "details": null, "correlation_id": "..." } }
```

## Auth

| Method | Path                              | Body                              | Description                |
|--------|-----------------------------------|------------------------------------|----------------------------|
| POST   | `/auth/register`                  | `{email, password, full_name?}`    | Create account             |
| POST   | `/auth/login`                     | `{email, password}`                | Returns access+refresh     |
| POST   | `/auth/refresh`                   | `{refresh_token}`                  | Rotate tokens              |
| POST   | `/auth/logout`                    | `{refresh_token}`                  | Revoke session             |
| GET    | `/auth/me`                        | —                                  | Current user               |
| POST   | `/auth/password-reset/request`    | `{email}`                          | Send reset link            |
| POST   | `/auth/password-reset/confirm`    | `{token, new_password}`            | Set new password           |
| POST   | `/auth/email/verify`              | `{token}`                          | Confirm email              |
| GET    | `/auth/oauth/google/login`        | —                                  | Begin OAuth                |
| GET    | `/auth/oauth/google/callback`     | `?code=`                            | OAuth callback             |
| GET    | `/auth/oauth/facebook/login`      | —                                  | Begin OAuth                |
| GET    | `/auth/oauth/facebook/callback`   | `?code=`                            | OAuth callback             |

## Users

| Method | Path        | Description           |
|--------|-------------|-----------------------|
| GET    | `/users/me` | Current user profile  |
| PATCH  | `/users/me` | Update profile / prefs|

## Chat

| Method | Path                                | Description                              |
|--------|-------------------------------------|------------------------------------------|
| GET    | `/chat/conversations`               | List conversations                       |
| POST   | `/chat/conversations`               | Create conversation                      |
| GET    | `/chat/conversations/{id}`          | Messages                                  |
| PATCH  | `/chat/conversations/{id}?title=`   | Rename                                    |
| DELETE | `/chat/conversations/{id}`          | Delete                                    |
| POST   | `/chat/send`                        | Send message (blocking)                  |
| POST   | `/chat/stream`                      | Send message (SSE streaming)             |
| WS     | `/ws/chat?token=<jwt>`              | Bidirectional streaming chat              |

## Outfits

| Method | Path                              | Description                       |
|--------|-----------------------------------|-----------------------------------|
| GET    | `/outfits?style=…&season=…`       | Paginated catalog                  |
| GET    | `/outfits/trending`               | Trending list                      |
| GET    | `/outfits/{id}`                   | Get one                            |
| GET    | `/outfits/me/favorites`           | User favorites                     |
| POST   | `/outfits/{id}/favorite`          | Toggle favorite                    |

## Recommendations

| Method | Path                       | Body / Params                                     | Description           |
|--------|----------------------------|---------------------------------------------------|-----------------------|
| POST   | `/recommendations`         | `{query, top_k?, use_weather?, filters?, …}`      | Generate recs         |
| GET    | `/recommendations/history` | `?limit=`                                         | Past recommendations  |
| POST   | `/recommendations/feedback`| `{recommendation_id, rating, label, comment}`     | Log feedback          |

## Trends

| Method | Path                         | Description       |
|--------|------------------------------|-------------------|
| GET    | `/trends?season=&limit=`     | Editorial trends  |

## Uploads

| Method | Path                | Description                              |
|--------|---------------------|------------------------------------------|
| POST   | `/uploads/image`    | Upload + analyze image (multipart/form-data) |

## Admin (RBAC: admin or super_admin)

| Method | Path                        | Description                |
|--------|-----------------------------|----------------------------|
| GET    | `/admin/overview`           | Aggregate metrics          |
| GET    | `/admin/users?q=&role=`     | Paginated user list        |
| PATCH  | `/admin/users/{id}`         | Update user (role/active)  |
| DELETE | `/admin/users/{id}`         | Delete user                |
| GET    | `/admin/usage?limit=`       | Recent API usage           |
| GET    | `/admin/events?limit=`      | Event log                  |

## Analytics (RBAC: admin)

| Method | Path                        | Description           |
|--------|-----------------------------|-----------------------|
| GET    | `/analytics/overview`       | Same as admin/overview|
| GET    | `/analytics/dau?days=`      | Daily active users    |
| GET    | `/analytics/popular-styles` | Top favorite styles   |
| GET    | `/analytics/ctr`            | Recommendation CTR    |
