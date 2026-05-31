"""API v1 aggregator."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    chat,
    outfits,
    recommendations,
    trends,
    upload,
    users,
)

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(outfits.router, prefix="/outfits", tags=["outfits"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
router.include_router(trends.router, prefix="/trends", tags=["trends"])
router.include_router(upload.router, prefix="/uploads", tags=["uploads"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
