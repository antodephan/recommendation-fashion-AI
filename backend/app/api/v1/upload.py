"""File uploads (images) with validation + optional vision analysis."""

from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import ValidationError
from app.core.logger import logger

from ai_engine.vision import describe_image, is_valid_image_bytes

router = APIRouter()

_VISION_TIMEOUT_SEC = 25.0


@router.post("/image")
async def upload_image(user: CurrentUser, file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError("File too large")

    if not is_valid_image_bytes(contents, file.content_type):
        raise ValidationError(
            f"Unsupported or invalid image (type={file.content_type or 'unknown'}). "
            "Use JPEG, PNG, or WebP."
        )

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}:
        suffix = ".jpg"
    name = f"{secrets.token_hex(12)}{suffix}"
    path = Path(settings.UPLOAD_DIR) / name
    path.write_bytes(contents)

    description: dict = {}
    try:
        description = await asyncio.wait_for(
            describe_image(contents),
            timeout=_VISION_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Vision analysis timed out for {name}")
    except Exception as exc:
        logger.warning(f"Vision analysis skipped for {name}: {exc}")

    logger.info(f"User {user.email} uploaded {path.name}")
    return {
        "url": f"/static/uploads/{name}",
        "filename": name,
        "description": description,
    }
