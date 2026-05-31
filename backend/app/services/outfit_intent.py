"""Detect when chat should trigger outfit recommendations."""

from __future__ import annotations

import re

_OUTFIT_KEYWORDS = re.compile(
    r"\b("
    r"gợi\s*ý|goi\s*y|outfit|recommend|mặc\s*gì|mac\s*gi|phối\s*đồ|phoi\s*do|"
    r"what\s+should\s+i\s+wear|style\s+me|suggest|wardrobe|look\s+for|"
    r"quần\s*áo|quan\s*ao|thời\s*trang|thoi\s*trang|dress|wear"
    r")\b",
    re.IGNORECASE,
)


def needs_outfit_recommendation(content: str, *, has_image: bool = False) -> bool:
    if has_image:
        return True
    text = (content or "").strip()
    if len(text) < 3:
        return False
    return bool(_OUTFIT_KEYWORDS.search(text))
