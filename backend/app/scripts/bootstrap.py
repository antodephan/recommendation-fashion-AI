"""Idempotent bootstrap: ensure a Super Admin user exists + seed data.

Run via:
    python -m app.scripts.bootstrap
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import settings
from app.core.logger import configure_logging, logger
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole

from app.scripts.import_hm_catalog import import_hm_catalog
from app.scripts.seed_outfits import seed_outfits
from app.scripts.seed_trends import seed_trends
from app.scripts.seed_kb import seed_knowledge_base


async def ensure_superadmin() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == settings.SUPERADMIN_EMAIL.lower()))
        existing = result.scalar_one_or_none()
        if existing:
            if existing.role != UserRole.SUPERADMIN:
                existing.role = UserRole.SUPERADMIN
                await db.commit()
            logger.info(f"Superadmin already exists: {existing.email}")
            return
        user = User(
            email=settings.SUPERADMIN_EMAIL.lower(),
            full_name="Super Admin",
            hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
            role=UserRole.SUPERADMIN,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        await db.commit()
        logger.info(f"Created superadmin: {user.email}")


async def _safe_step(name: str, coro) -> None:
    """Run a bootstrap step; log and continue on failure so the API can still start."""
    try:
        await coro
    except Exception as exc:
        logger.warning(f"Bootstrap step '{name}' failed (non-fatal): {exc}")


async def main() -> None:
    configure_logging()
    logger.info("=== Bootstrap starting ===")
    await ensure_superadmin()
    await _safe_step("outfits", seed_outfits())
    if settings.HM_CATALOG_AUTO_IMPORT and settings.RAPIDAPI_KEY:
        await _safe_step(
            "hm_catalog",
            import_hm_catalog(limit=settings.HM_CATALOG_IMPORT_LIMIT, force=False),
        )
    elif settings.CATALOG_AUTO_IMPORT:
        from app.scripts.import_catalog import import_catalog

        await _safe_step(
            "catalog",
            import_catalog(limit=settings.CATALOG_IMPORT_LIMIT, force=False),
        )
    if settings.RAPIDAPI_KEY:
        from app.scripts.sync_hm_trends import sync_hm_trends

        await _safe_step("hm_trends", sync_hm_trends())
    else:
        await _safe_step("trends", seed_trends())
    await _safe_step("kb", seed_knowledge_base())
    logger.info("=== Bootstrap done ===")


if __name__ == "__main__":
    asyncio.run(main())
