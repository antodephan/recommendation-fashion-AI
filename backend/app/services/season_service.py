"""Season inference from weather, calendar, and location (VN-aware)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def infer_season(
    temp_c: float | None = None,
    month: int | None = None,
    *,
    location: str | None = None,
) -> str:
    """Map weather + month to a fashion season label."""
    if month is None:
        month = datetime.now(timezone.utc).month

    loc = (location or "").lower()
    tropical = any(
        hint in loc
        for hint in (
            "vietnam",
            "việt",
            "ho chi minh",
            "hanoi",
            "hà nội",
            "saigon",
            "sài gòn",
            "bangkok",
            "singapore",
            "jakarta",
            "manila",
        )
    )

    if temp_c is not None:
        if tropical:
            if temp_c >= 30:
                return "summer"
            if temp_c >= 24:
                return "spring"
            if temp_c >= 18:
                return "autumn"
            return "winter"
        if temp_c >= 26:
            return "summer"
        if temp_c >= 15:
            return "spring" if month in (3, 4, 5, 9, 10, 11) else "autumn"
        return "winter"

    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def season_context_block(
    weather: dict[str, Any] | None,
    season: str | None,
    hm_region: str | None = None,
) -> str:
    lines: list[str] = []
    if weather:
        lines.append(
            f"- Weather: {weather.get('summary')} • {weather.get('temp_c')}°C in {weather.get('location')}"
        )
    if season:
        lines.append(f"- Season: {season}")
    if hm_region:
        lines.append(f"- H&M catalog region: {hm_region}")
    return "\n".join(lines) or "- (no environment context)"
