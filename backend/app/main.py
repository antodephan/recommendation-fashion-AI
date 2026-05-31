"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1 import router as v1_router
from app.api.ws import router as ws_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import configure_logging, logger
from app.core.redis_client import close_redis, get_redis
from app.middleware.request_context import (
    CorrelationMiddleware,
    SecurityHeadersMiddleware,
)

from ai_engine.vector_store import ensure_collections


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{__version__} ({settings.ENVIRONMENT})")
    # Ensure data dirs
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    # Bootstrap Redis
    try:
        await get_redis().ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning(f"Redis not reachable at boot: {exc}")
    # Ensure Qdrant collections
    try:
        await ensure_collections()
        logger.info("Qdrant collections ready")
    except Exception as exc:
        logger.warning(f"Qdrant init failed (will retry lazily): {exc}")

    scheduler = None
    try:
        from app.services.hm_scheduler import start_hm_scheduler

        scheduler = start_hm_scheduler()
    except Exception as exc:
        logger.warning(f"H&M scheduler not started: {exc}")

    async def _bootstrap_background() -> None:
        try:
            from app.scripts.bootstrap import main as bootstrap_main

            await bootstrap_main()
        except Exception as exc:
            logger.warning(f"Background bootstrap failed: {exc}")

    bootstrap_task = asyncio.create_task(_bootstrap_background())

    yield

    bootstrap_task.cancel()
    try:
        await bootstrap_task
    except asyncio.CancelledError:
        pass

    if scheduler:
        scheduler.shutdown(wait=False)

    await close_redis()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---- middleware (order matters: outermost first) ----
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time"],
    )

    register_exception_handlers(app)

    # ---- routes ----
    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ws_router)

    # static uploads
    uploads_path = Path(settings.UPLOAD_DIR)
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    catalog_images = Path(settings.FASHION_IMAGES_DIR)
    if catalog_images.is_dir():
        app.mount("/static/catalog", StaticFiles(directory=str(catalog_images)), name="catalog")

    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse(
            {
                "name": settings.PROJECT_NAME,
                "version": __version__,
                "environment": settings.ENVIRONMENT,
                "docs": "/docs",
            }
        )

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
