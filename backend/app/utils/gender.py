"""Shared gender normalization and matching for recommendations."""

from __future__ import annotations

MALE_ALIASES = frozenset({"male", "men", "man", "m", "boy", "boys", "nam"})
FEMALE_ALIASES = frozenset({"female", "women", "woman", "f", "ladies", "lady", "girl", "girls", "nu", "nữ"})
UNISEX_ALIASES = frozenset({"unisex", "all", "neutral", "both"})


def normalize_gender(raw: str | None) -> str | None:
    """Return canonical gender: male, female, unisex, or None."""
    if not raw:
        return None
    g = str(raw).strip().lower()
    if g in MALE_ALIASES:
        return "male"
    if g in FEMALE_ALIASES:
        return "female"
    if g in UNISEX_ALIASES:
        return "unisex"
    return None


def allowed_outfit_genders(user_gender: str | None) -> set[str] | None:
    """Outfit.gender values suitable for the user (includes unisex)."""
    canonical = normalize_gender(user_gender)
    if canonical == "male":
        return {"male", "unisex"}
    if canonical == "female":
        return {"female", "unisex"}
    return None


def gender_matches_user(
    user_gender: str | None,
    item_gender: str | None,
    *,
    allow_unisex: bool = True,
) -> bool:
    """True when an outfit/product gender fits the user's profile."""
    user = normalize_gender(user_gender)
    if not user:
        return True
    item = normalize_gender(item_gender)
    if not item:
        return allow_unisex
    if item == user:
        return True
    return allow_unisex and item == "unisex"


def gender_sql_values(user_gender: str | None) -> list[str] | None:
    """Values for SQL IN (...) filter on Outfit.gender."""
    allowed = allowed_outfit_genders(user_gender)
    if not allowed:
        return None
    return sorted(allowed)
