"""Background scheduler for H&M catalog and trends sync."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.core.logger import logger


def start_hm_scheduler() -> AsyncIOScheduler | None:
    if not settings.HM_SCHEDULER_ENABLED or not settings.RAPIDAPI_KEY:
        return None

    scheduler = AsyncIOScheduler()

    async def _catalog_job() -> None:
        from app.scripts.import_hm_catalog import import_hm_catalog

        try:
            await import_hm_catalog(force=False)
        except Exception as exc:
            logger.warning(f"Scheduled H&M catalog sync failed: {exc}")

    async def _trends_job() -> None:
        from app.scripts.sync_hm_trends import sync_hm_trends

        try:
            await sync_hm_trends()
        except Exception as exc:
            logger.warning(f"Scheduled H&M trends sync failed: {exc}")

    interval_hours = max(6, settings.HM_TRENDS_SYNC_INTERVAL_HOURS)

    scheduler.add_job(_catalog_job, "interval", hours=24, id="hm_catalog_sync", replace_existing=True)
    scheduler.add_job(
        _trends_job, "interval", hours=interval_hours, id="hm_trends_sync", replace_existing=True
    )
    scheduler.start()
    logger.info(f"H&M scheduler started (catalog=24h, trends={interval_hours}h)")
    return scheduler
