"""Map user style preferences (VI/EN) to searchable product keywords."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# User-facing style label -> English product/catalog keywords
STYLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    # English canonical styles
    "minimalist": ("minimal", "minimalist", "monochrome", "clean", "simple"),
    "casual": ("casual", "everyday", "relaxed", "cotton", "tee", "t-shirt"),
    "streetwear": ("street", "streetwear", "cargo", "graphic", "hoodie", "oversized", "boxy"),
    "formal": ("formal", "tailored", "suit", "blazer", "dress shirt", "trouser"),
    "smart-casual": ("smart", "chino", "linen", "polo", "oxford"),
    "athleisure": ("athleisure", "sport", "sportswear", "track", "jogger", "training", "gym"),
    "sporty": ("sport", "sportswear", "athletic", "track", "jogger", "training", "active", "mesh"),
    "vintage": ("vintage", "retro", "denim", "wash"),
    "bohemian": ("boho", "bohemian", "floral", "flowy", "embroidered"),
    "athletic": ("athletic", "performance", "sport", "training", "dry"),
    "oversized": ("oversized", "oversize", "boxy", "loose", "wide", "baggy"),
    "basic": ("basic", "essential", "plain", "regular fit", "crew"),
    "clean": ("clean", "minimal", "plain", "simple"),
    "relaxed": ("relaxed", "loose", "comfort", "easy"),
    "masculine": ("men", "masculine", "structured", "straight"),
    # Vietnamese preferences
    "thoải mái": ("relaxed", "loose", "comfort", "soft", "cotton", "easy", "wide"),
    "thoai mai": ("relaxed", "loose", "comfort", "soft", "cotton", "easy", "wide"),
    "dễ mặc": ("easy", "comfort", "casual", "cotton", "relaxed"),
    "de mac": ("easy", "comfort", "casual", "cotton", "relaxed"),
    "thoải mái và dễ mặc": ("relaxed", "comfort", "casual", "cotton", "easy"),
    "năng động": ("sport", "active", "athletic", "dynamic", "training"),
    "nang dong": ("sport", "active", "athletic", "dynamic", "training"),
    "thoáng": ("linen", "lightweight", "breathable", "mesh", "airy"),
    "thoang": ("linen", "lightweight", "breathable", "mesh", "airy"),
    "nhanh khô": ("dry", "quick", "performance", "sport", "active"),
    "basic sporty": ("sport", "basic", "track", "jogger", "tee"),
    "sạch sẽ": ("clean", "plain", "minimal", "simple"),
    "sach se": ("clean", "plain", "minimal", "simple"),
    "hơi oversized": ("oversized", "loose", "boxy", "relaxed"),
    "lên hình đẹp": ("structured", "tailored", "clean", "smart"),
    "len hinh dep": ("structured", "tailored", "clean", "smart"),
    "straight fit": ("straight", "slim", "regular"),
    "bomber": ("bomber", "jacket", "aviator"),
}

# Map free-text style to canonical DB / trend style_type
CANONICAL_STYLE: dict[str, str] = {
    "sporty": "athleisure",
    "sport": "athleisure",
    "năng động": "athleisure",
    "nang dong": "athleisure",
    "basic sporty": "athleisure",
    "athleisure": "athleisure",
    "athletic": "athleisure",
    "streetwear": "streetwear",
    "street": "streetwear",
    "casual": "casual",
    "thoải mái": "casual",
    "thoai mai": "casual",
    "dễ mặc": "casual",
    "de mac": "casual",
    "thoải mái và dễ mặc": "casual",
    "relaxed": "casual",
    "basic": "casual",
    "clean": "minimalist",
    "sạch sẽ": "minimalist",
    "minimalist": "minimalist",
    "formal": "formal",
    "smart-casual": "smart-casual",
    "oversized": "streetwear",
    "hơi oversized": "streetwear",
    "vintage": "vintage",
    "bohemian": "bohemian",
    "bomber": "streetwear",
}

# H&M category hints per canonical style (section prefix added at runtime)
STYLE_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "athleisure": ("sportswear", "hoodie", "jogger", "track", "sweatshirt", "shorts"),
    "streetwear": ("hoodie", "cargo", "tshirt", "sweatshirt", "jacket"),
    "casual": ("tshirt", "chino", "shirt", "jeans", "trouser"),
    "formal": ("shirt", "blazer", "suit", "trouser", "chino"),
    "minimalist": ("shirt", "trouser", "tshirt", "blazer"),
    "smart-casual": ("shirt", "chino", "polo", "linen"),
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _normalize_label(text: str) -> str:
    return _strip_accents(str(text or "").strip().lower())


def expand_style_keywords(styles: list[str] | None) -> set[str]:
    """English keywords derived from user style labels."""
    keywords: set[str] = set()
    for raw in styles or []:
        label = str(raw).strip().lower()
        if not label:
            continue
        keywords.add(label)
        keywords.add(_normalize_label(label))
        if label in STYLE_KEYWORDS:
            keywords.update(STYLE_KEYWORDS[label])
        norm = _normalize_label(label)
        if norm in STYLE_KEYWORDS:
            keywords.update(STYLE_KEYWORDS[norm])
        # Partial map: match keys contained in long phrases
        for key, vals in STYLE_KEYWORDS.items():
            if key in label or label in key:
                keywords.update(vals)
                keywords.add(key)
    return {k.lower() for k in keywords if k and len(k) > 2}


def resolve_canonical_styles(styles: list[str] | None) -> list[str]:
    """Canonical outfit/trend styles for SQL filters."""
    out: list[str] = []
    for raw in styles or []:
        label = str(raw).strip().lower()
        norm = _normalize_label(label)
        for candidate in (label, norm):
            if candidate in CANONICAL_STYLE:
                canon = CANONICAL_STYLE[candidate]
                if canon not in out:
                    out.append(canon)
                break
        else:
            for key, canon in CANONICAL_STYLE.items():
                if key in label or label in key:
                    if canon not in out:
                        out.append(canon)
                    break
    return out[:6]


def primary_canonical_style(styles: list[str] | None) -> str | None:
    resolved = resolve_canonical_styles(styles)
    return resolved[0] if resolved else None


def style_match_score(
    styles: list[str] | None,
    blob: str,
    *,
    trend_tags: set[str] | None = None,
    trend_style_type: str | None = None,
) -> float:
    """Score 0–1 for how well product/trend text matches user styles."""
    if not styles and not trend_tags:
        return 0.0
    text = (blob or "").lower()
    keywords = expand_style_keywords(styles)
    if not keywords:
        return 0.0

    hits = 0
    checked = 0
    for kw in keywords:
        if len(kw) < 3:
            continue
        checked += 1
        if kw in text:
            hits += 1
        elif " " in kw and all(part in text for part in kw.split() if len(part) > 2):
            hits += 1

    if trend_tags:
        trend_hits = sum(1 for t in trend_tags if t in keywords or any(t in k or k in t for k in keywords))
        if trend_hits:
            hits += trend_hits
            checked += max(len(trend_tags), 1)

    if trend_style_type:
        canon = resolve_canonical_styles(styles)
        if trend_style_type.lower() in canon or trend_style_type.lower() in text:
            hits += 2
            checked += 2

    if checked == 0:
        return 0.0
    return min(1.0, hits / max(checked * 0.35, 1))


def style_category_hints(styles: list[str] | None, section: str = "men") -> list[str]:
    """H&M category id fragments to prioritize for user styles."""
    section = (section or "men").lower()
    hints: list[str] = []
    for canon in resolve_canonical_styles(styles):
        for hint in STYLE_CATEGORY_HINTS.get(canon, ()):
            hints.append(f"{section}_{hint}" if not hint.startswith(section) else hint)
            hints.append(hint)
    return list(dict.fromkeys(hints))


def profile_style_tokens(profile: dict[str, Any]) -> set[str]:
    """Search tokens from profile including expanded style keywords."""
    tokens: set[str] = set()
    styles = profile.get("styles") or []
    tokens |= expand_style_keywords(styles)
    for key in ("colors", "brands", "avoid"):
        for val in profile.get(key) or []:
            s = str(val).strip().lower()
            if len(s) > 2:
                tokens.add(s)
                tokens.add(_normalize_label(s))
    return tokens


def tokenize_text(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[\w]+", text.lower(), flags=re.UNICODE) if len(tok) > 2}
