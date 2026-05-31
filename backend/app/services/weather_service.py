"""Weather lookup via OpenWeather (cached)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.core.cache import cache_get, cache_set
from app.core.logger import logger


class WeatherService:
    async def current(self, location: str) -> dict[str, Any] | None:
        if not location:
            return None
        cache_key = f"weather:{location.lower()}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        if not settings.OPENWEATHER_API_KEY:
            return {
                "location": location,
                "temp_c": 18.0,
                "summary": "mild and partly cloudy",
                "humidity": 60,
                "wind_kph": 8,
            }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": location, "units": "metric", "appid": settings.OPENWEATHER_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning(f"Weather fetch failed for '{location}': {exc}")
            return None

        result = {
            "location": data.get("name", location),
            "temp_c": data.get("main", {}).get("temp"),
            "summary": (data.get("weather", [{}])[0] or {}).get("description"),
            "humidity": data.get("main", {}).get("humidity"),
            "wind_kph": (data.get("wind", {}).get("speed", 0) or 0) * 3.6,
        }
        await cache_set(cache_key, result, ttl=600)
        return result
