"""Centralized application configuration.

All settings are loaded from environment variables (or a local `.env`)
and validated through Pydantic. The resulting `settings` singleton is
imported throughout the codebase via `from app.config import settings`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    # -- General --------------------------------------------------------
    PROJECT_NAME: str = "AI Fashion Recommendation System"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # -- CORS (comma-separated in .env, e.g. http://localhost:3000,http://localhost) --
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost"

    # -- Security -------------------------------------------------------
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    COOKIE_DOMAIN: str = "localhost"
    COOKIE_SECURE: bool = False

    # -- PostgreSQL -----------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+asyncpg://fashion:fashion@localhost:5432/fashion"
    )

    # -- Redis ----------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # -- Qdrant ---------------------------------------------------------
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_OUTFITS: str = "outfits"
    QDRANT_COLLECTION_PRODUCTS: str = "products"
    QDRANT_COLLECTION_USERS: str = "user_profiles"
    QDRANT_COLLECTION_CHATS: str = "chat_memory"
    QDRANT_COLLECTION_KB: str = "fashion_kb"

    # -- OpenAI ---------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-5.4-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_VISION_MODEL: str = "gpt-5.4-mini"
    EMBEDDING_DIM: int = 1536

    # -- RAG ------------------------------------------------------------
    RAG_QUERY_REWRITE_ENABLED: bool = True
    RAG_RETRIEVAL_MULTIPLIER: int = 3
    RAG_LEXICAL_RERANK_WEIGHT: float = 0.25
    RAG_PROFILE_RERANK_WEIGHT: float = 0.15

    # -- OAuth ----------------------------------------------------------
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    FACEBOOK_REDIRECT_URI: str = ""

    # -- Email (SMTP) ---------------------------------------------------
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@couture.ai"
    SMTP_FROM_NAME: str = "Couture AI"

    # -- Weather --------------------------------------------------------
    OPENWEATHER_API_KEY: str = ""

    # -- Sentry ---------------------------------------------------------
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # -- Admin bootstrap ------------------------------------------------
    SUPERADMIN_EMAIL: str = "admin@couture.ai"
    SUPERADMIN_PASSWORD: str = "changeme123!"

    # -- Upload / files -------------------------------------------------
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: List[str] = Field(
        default_factory=lambda: [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
            "image/pjpeg",
        ]
    )

    # -- Legacy fashion dataset (Fashion-Recomendation-AI-ChatBot) ------
    FASHION_LEGACY_DIR: str = "../Fashion-Recomendation-AI-ChatBot"
    FASHION_CSV_PATH: str = "../Fashion-Recomendation-AI-ChatBot/data/styles.csv"
    FASHION_IMAGES_DIR: str = "../Fashion-Recomendation-AI-ChatBot/data/images"
    CATALOG_IMPORT_LIMIT: int = 3000
    CATALOG_AUTO_IMPORT: bool = False

    # -- RapidAPI H&M ---------------------------------------------------
    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HM_HOST: str = "apidojo-hm-hennes-mauritz-v1.p.rapidapi.com"
    HM_REGION: str = "vn"
    HM_CATALOG_IMPORT_LIMIT: int = 2000
    HM_CATALOG_SECTIONS: str = "ladies,men"
    HM_CATALOG_AUTO_IMPORT: bool = True
    HM_TRENDS_SYNC_INTERVAL_HOURS: int = 72
    HM_SCHEDULER_ENABLED: bool = True

    # -- Rate limiting --------------------------------------------------
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_CHAT: str = "30/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator(
        "RAPIDAPI_KEY",
        "OPENWEATHER_API_KEY",
        "JWT_SECRET",
        "OPENAI_API_KEY",
        mode="before",
    )
    @classmethod
    def _strip_secrets(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Parse BACKEND_CORS_ORIGINS into a list for FastAPI CORSMiddleware."""
        raw = (self.BACKEND_CORS_ORIGINS or "").strip()
        if not raw:
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost",
                "http://127.0.0.1",
            ]
        if raw.startswith("["):
            return json.loads(raw)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
