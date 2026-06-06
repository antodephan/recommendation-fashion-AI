"""Helpers to record H&M sync job runs."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from sqlalchemy import desc, select
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


async def last_successful_sync_at(
    db: AsyncSession,
    job_type: SyncJobType,
) -> datetime | None:
    result = await db.execute(
        select(SyncRun.created_at)
        .where(SyncRun.job_type == job_type, SyncRun.status == SyncStatus.SUCCESS)
        .order_by(desc(SyncRun.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def should_run_scheduled_sync(
    db: AsyncSession,
    job_type: SyncJobType,
    interval_hours: int,
    *,
    force: bool = False,
) -> bool:
    """Return True when enough time has passed since the last successful sync."""
    if force:
        return True
    from datetime import datetime, timedelta, timezone

    last = await last_successful_sync_at(db, job_type)
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - last
    return elapsed >= timedelta(hours=max(1, interval_hours))
