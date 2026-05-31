"""Outfit and recommendation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OutfitItemRead(BaseModel):
    id: uuid.UUID
    category: str
    name: str
    brand: str | None = None
    color: str | None = None
    material: str | None = None
    price: float | None = None
    image_url: str | None = None
    product_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OutfitRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    style: str | None = None
    season: str | None = None
    gender: str | None = None
    occasion: str | None = None
    colors: list[str] = []
    materials: list[str] = []
    tags: list[str] = []
    brand: str | None = None
    price: float | None = None
    currency: str = "USD"
    rating: float = 0.0
    popularity: int = 0
    items: list[OutfitItemRead] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutfitFilters(BaseModel):
    style: str | None = None
    season: str | None = None
    gender: str | None = None
    occasion: str | None = None
    body_type: str | None = None
    color: str | None = None
    brand: str | None = None
    max_price: float | None = None
    tags: list[str] = Field(default_factory=list)
    query: str | None = None


class RecommendationRequest(BaseModel):
    query: str = Field(description="Free-text intent, e.g. 'minimalist work outfit for autumn'")
    conversation_id: uuid.UUID | None = None
    filters: OutfitFilters | None = None
    top_k: int = 6
    use_weather: bool = True
    location: str | None = None
    image_url: str | None = Field(
        default=None,
        description="Inspiration photo (/static/uploads/... or /static/catalog/...)",
    )


class RecommendationItem(BaseModel):
    outfit_id: uuid.UUID
    name: str
    image_url: str | None = None
    score: float
    why: str
    tags: list[str] = []
    price: float | None = None
    currency: str = "USD"
    source_url: str | None = None


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    query: str
    reasoning: str
    confidence: float
    trend_score: float
    items: list[RecommendationItem]
    weather: dict[str, Any] | None = None
    created_at: datetime


class RecommendationFeedbackIn(BaseModel):
    recommendation_id: uuid.UUID
    rating: int = Field(default=0, ge=-1, le=5)
    label: str | None = None
    comment: str | None = None
