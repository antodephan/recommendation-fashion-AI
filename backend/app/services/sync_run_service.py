"""Helpers to record H&M sync job runs."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_run import SyncJobType, SyncRun, SyncStatus


@asynccontextmanager
async def sync_run_context(
    db: AsyncSession,
    job_type: SyncJobType,
    *,
    region: str | None = None,
) -> AsyncIterator[SyncRun]:
    run = SyncRun(
        id=uuid.uuid4(),
        job_type=job_type,
        status=SyncStatus.RUNNING,
        region=region,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    started = time.perf_counter()
    try:
        yield run
        run.status = SyncStatus.SUCCESS
    except Exception as exc:
        run.status = SyncStatus.FAILED
        run.error_message = str(exc)[:4000]
        raise
    finally:
        run.duration_ms = (time.perf_counter() - started) * 1000
        await db.commit()


async def finalize_sync_run(
    db: AsyncSession,
    run: SyncRun,
    *,
    items_added: int = 0,
    items_updated: int = 0,
    items_failed: int = 0,
    meta: dict[str, Any] | None = None,
) -> None:
    run.items_added = items_added
    run.items_updated = items_updated
    run.items_failed = items_failed
    if meta:
        run.meta = {**(run.meta or {}), **meta}
    await db.commit()
