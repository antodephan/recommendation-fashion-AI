"""Lightweight input sanitization helpers."""

from __future__ import annotations

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "")


def sanitize_user_text(text: str, *, max_len: int = 5000) -> str:
    """Remove HTML tags + control chars + truncate."""
    cleaned = _CONTROL_CHARS.sub("", strip_html(text or ""))
    return cleaned.strip()[:max_len]
