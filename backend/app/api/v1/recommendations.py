"""Recommendation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limit
from app.schemas.common import Message
from app.schemas.outfit import (
    RecommendationFeedbackIn,
    RecommendationRequest,
    RecommendationResponse,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.post(
    "",
    response_model=RecommendationResponse,
    dependencies=[Depends(rate_limit(settings.RATE_LIMIT_CHAT, scope="rec"))],
)
async def recommend(payload: RecommendationRequest, user: CurrentUser, db: DbSession):
    service = RecommendationService(db)
    return await service.recommend(user, payload)


@router.get("/history")
async def history(user: CurrentUser, db: DbSession, limit: int = 30):
    service = RecommendationService(db)
    history = await service.history(user, limit=limit)
    return [
        {
            "id": str(r.id),
            "query": r.query,
            "reasoning": r.reasoning,
            "confidence": r.confidence,
            "trend_score": r.trend_score,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in history
    ]


@router.post("/feedback", response_model=Message)
async def feedback(payload: RecommendationFeedbackIn, user: CurrentUser, db: DbSession):
    service = RecommendationService(db)
    await service.feedback(
        user, payload.recommendation_id, payload.rating, payload.label, payload.comment
    )
    return Message(message="thanks")
