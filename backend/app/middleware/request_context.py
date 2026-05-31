"""Attach a correlation id to every request, log timing and persist usage."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logger import correlation_id, logger


class CorrelationMiddleware(BaseHTTPMiddleware):
    HEADER = "X-Correlation-ID"

    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get(self.HEADER) or uuid.uuid4().hex
        token = correlation_id.set(cid)
        request.state.correlation_id = cid

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                f"REQ-FAIL {request.method} {request.url.path} ({elapsed:.1f}ms)"
            )
            raise
        finally:
            correlation_id.reset(token)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[self.HEADER] = cid
        response.headers["X-Response-Time"] = f"{elapsed_ms:.2f}ms"
        logger.info(
            f"REQ {request.method} {request.url.path} "
            f"-> {response.status_code} ({elapsed_ms:.1f}ms)"
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply common security headers."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        return response
