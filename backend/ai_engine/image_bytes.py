"""Load image bytes from upload URLs or local paths."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from app.config import settings


def load_image_bytes(image_url: str) -> bytes:
    """Resolve an image URL or path to raw bytes (uploads + catalog static)."""
    if image_url.startswith("data:"):
        import base64

        header, _, b64 = image_url.partition(",")
        return base64.b64decode(b64)

    parsed = urlparse(image_url)
    path = parsed.path if parsed.scheme else image_url

    if "/static/uploads/" in path:
        name = path.split("/static/uploads/", 1)[1].split("?")[0]
        file_path = Path(settings.UPLOAD_DIR) / name
    elif "/static/catalog/" in path:
        name = path.split("/static/catalog/", 1)[1].split("?")[0]
        file_path = Path(settings.FASHION_IMAGES_DIR) / name
    elif path.startswith("/static/catalog/"):
        name = path[len("/static/catalog/") :].split("?")[0]
        file_path = Path(settings.FASHION_IMAGES_DIR) / name
    else:
        raise ValueError(f"Unsupported image URL: {image_url}")

    if not file_path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")
    return file_path.read_bytes()
