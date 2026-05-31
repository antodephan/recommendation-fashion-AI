"""Multimodal vision helpers (GPT-4 vision API + lightweight color extraction)."""

from __future__ import annotations

import base64
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import embed_text, get_openai

_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_LOCAL_HOSTS = frozenset(
    {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "fashion-backend"}
)

_ALLOWED_UPLOAD_TYPES = frozenset(
    t.lower()
    for t in (
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "image/pjpeg",
        "application/octet-stream",
    )
)


def is_valid_image_bytes(data: bytes, content_type: str | None = None) -> bool:
    """Accept common photo types; fall back to Pillow decode when MIME is missing."""
    if content_type and content_type.lower() in _ALLOWED_UPLOAD_TYPES:
        try:
            with Image.open(BytesIO(data)) as img:
                img.verify()
            return True
        except Exception:
            pass
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:
        return False


def resolve_image_url_for_llm(image_url: str) -> str:
    """Convert local upload URLs to base64 data URLs OpenAI can read.

    OpenAI downloads ``image_url`` from the public internet. ``localhost`` URLs
    only exist on your machine, so chat with uploaded photos must inline bytes.
    """
    if not image_url:
        return image_url
    if image_url.startswith("data:"):
        return image_url

    parsed = urlparse(image_url)
    path = parsed.path or image_url

    marker = "/static/uploads/"
    if marker in path:
        filename = path.split(marker, 1)[1].split("?")[0]
        file_path = Path(settings.UPLOAD_DIR) / filename
        if file_path.is_file():
            raw = file_path.read_bytes()
            mime = _MIME_BY_SUFFIX.get(file_path.suffix.lower(), "image/jpeg")
            b64 = base64.b64encode(raw).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        logger.warning(f"Upload file missing for LLM: {file_path}")

    host = (parsed.hostname or "").lower()
    if host in _LOCAL_HOSTS and parsed.scheme in ("http", "https", ""):
        raise ValueError(f"Local image URL not found on disk: {image_url}")

    if image_url.startswith("https://") or image_url.startswith("http://"):
        return image_url

    raise ValueError(f"Cannot resolve image URL for LLM: {image_url}")


async def describe_image(image_bytes: bytes, *, hint: str | None = None) -> dict[str, Any]:
    """Use the vision-capable model to extract a structured fashion description."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    client = get_openai()
    prompt = (
        "Analyze this fashion image and return JSON with keys: "
        "items (list of clothing items: {category, color, material, style}), "
        "overall_style, dominant_colors (list of hex), suggested_tags (list)."
    )
    if hint:
        prompt += f"\nAdditional hint: {hint}"

    try:
        resp = await client.chat.completions.create(
            model=settings.OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        import json
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.warning(f"Vision describe failed: {exc}; falling back to color extraction")
        return {"items": [], "overall_style": None, "dominant_colors": extract_dominant_colors(image_bytes), "suggested_tags": []}


def extract_dominant_colors(image_bytes: bytes, top_k: int = 5) -> list[str]:
    """Naïve dominant-color extraction without sklearn — quantize and count."""
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img = img.resize((96, 96))
        pixels = list(img.getdata())
        # quantize each channel to 32 levels
        quantized = [
            (r >> 3, g >> 3, b >> 3) for (r, g, b) in pixels
        ]
        counts = Counter(quantized)
        result: list[str] = []
        for (r, g, b), _ in counts.most_common(top_k):
            result.append("#{:02x}{:02x}{:02x}".format(r << 3, g << 3, b << 3))
        return result
    except Exception as exc:
        logger.warning(f"Color extraction failed: {exc}")
        return []


async def embed_image_description(description: dict[str, Any]) -> list[float]:
    """Encode the textual representation of an image to a vector."""
    bits: list[str] = []
    if description.get("overall_style"):
        bits.append(f"style: {description['overall_style']}")
    if description.get("dominant_colors"):
        bits.append(f"colors: {', '.join(description['dominant_colors'])}")
    for item in description.get("items") or []:
        bits.append(
            f"{item.get('category','')}: {item.get('color','')} {item.get('material','')} {item.get('style','')}".strip()
        )
    if description.get("suggested_tags"):
        bits.append("tags: " + ", ".join(description["suggested_tags"]))
    text = ". ".join(b for b in bits if b)
    return await embed_text(text or "fashion outfit image")
