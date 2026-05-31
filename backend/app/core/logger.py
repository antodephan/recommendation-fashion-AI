"""Structured logging via Loguru with optional Sentry integration.

Designed for production: JSON-friendly format, correlation IDs and
graceful interception of the stdlib `logging` module used by
FastAPI / Uvicorn / SQLAlchemy.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger

from app.config import settings

# Correlation id propagated through async tasks (set by middleware).
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class _InterceptHandler(logging.Handler):
    """Forward stdlib logs to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _patcher(record: dict[str, Any]) -> None:
    record["extra"]["correlation_id"] = correlation_id.get()


def configure_logging() -> None:
    """Initialize loggers. Idempotent — safe to call multiple times."""
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<magenta>cid={extra[correlation_id]}</magenta> | "
        "<level>{message}</level>"
    )

    logger.configure(patcher=_patcher)
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=log_format,
        backtrace=True,
        diagnose=not settings.is_production,
        enqueue=True,
    )
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        rotation="20 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        format=log_format,
    )

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy.engine"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False

    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.starlette import StarletteIntegration
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                integrations=[StarletteIntegration(), FastApiIntegration()],
            )
            logger.info("Sentry initialized")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Failed to initialize Sentry: {exc}")


__all__ = ["logger", "configure_logging", "correlation_id"]
