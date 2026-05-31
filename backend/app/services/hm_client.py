"""RapidAPI H&M client with Redis cache and retry."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.core.cache import cache_get, cache_set
from app.core.logger import logger

_BASE = "https://apidojo-hm-hennes-mauritz-v1.p.rapidapi.com"

_VN_HINTS = ("vietnam", "vn", "việt", "viet nam", "asia")


class HMClientError(RuntimeError):
    """Raised when RapidAPI H&M returns an error payload."""


class HMClient:
    """Async client for apidojo H&M RapidAPI."""

    def __init__(self) -> None:
        key = (settings.RAPIDAPI_KEY or "").strip()
        self._headers = {
            "x-rapidapi-host": settings.RAPIDAPI_HM_HOST,
            "x-rapidapi-key": key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _check_response(data: Any) -> None:
        if not isinstance(data, dict):
            return
        if data.get("status") in (422, 403, 401):
            msg = data.get("message") or data.get("error") or "API validation error"
            raise HMClientError(str(msg))
        msg = data.get("message")
        if msg and isinstance(msg, str) and "subscribed" in msg.lower():
            raise HMClientError(msg)

    @retry(wait=wait_exponential(min=1, max=12), stop=stop_after_attempt(3), reraise=True)
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not (settings.RAPIDAPI_KEY or "").strip():
            raise RuntimeError("RAPIDAPI_KEY is not configured")
        url = f"{_BASE}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                return {}
            data = resp.json()
        self._check_response(data)
        return data

    @staticmethod
    def _unwrap_products(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            plp = data.get("plpList") or {}
            if isinstance(plp, dict):
                items = plp.get("productList")
                if isinstance(items, list):
                    return [x for x in items if isinstance(x, dict)]
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []

    @staticmethod
    def _flatten_countries(raw: Any) -> list[dict[str, Any]]:
        countries: list[dict[str, Any]] = []
        blocks = raw if isinstance(raw, list) else [raw]
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for c in block.get("countries") or []:
                if isinstance(c, dict) and c.get("code"):
                    countries.append(c)
            if block.get("code") and not block.get("countries"):
                countries.append(block)
        return countries

    @staticmethod
    def _walk_category_tags(nodes: Any, out: list[dict[str, str]]) -> None:
        if isinstance(nodes, list):
            for node in nodes:
                HMClient._walk_category_tags(node, out)
            return
        if not isinstance(nodes, dict):
            return
        name = str(nodes.get("CatName") or nodes.get("name") or "").strip()
        value = str(nodes.get("CategoryValue") or nodes.get("id") or "").strip()
        tags = nodes.get("tagCodes") or []
        category_id = tags[0] if tags else value
        if category_id and name:
            out.append({"name": name, "category_id": category_id, "value": value})
        for child_key in ("CategoriesArray", "categories", "children"):
            HMClient._walk_category_tags(nodes.get(child_key), out)

    async def list_regions(self) -> list[dict[str, Any]]:
        cache_key = "hm:v2:countries"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
        raw = await self._get("regions/list")
        countries = self._flatten_countries(raw)
        await cache_set(cache_key, countries, ttl=86400)
        return countries

    async def resolve_region(self, preferred: str | None = None) -> str:
        """Resolve H&M country code (e.g. us, gb). VN store not in API → fallback us."""
        preferred = (preferred or settings.HM_REGION or "vn").strip().lower()
        cache_key = f"hm:v2:region:{preferred}"
        cached = await cache_get(cache_key)
        if cached:
            return str(cached)

        countries = await self.list_regions()

        def _match(country: dict[str, Any]) -> str:
            return str(country.get("code") or "").lower()

        def _name(country: dict[str, Any]) -> str:
            return str(country.get("name") or "").lower()

        for c in countries:
            if _match(c) == preferred:
                code = _match(c)
                await cache_set(cache_key, code, ttl=86400)
                return code

        for c in countries:
            blob = f"{_match(c)} {_name(c)}"
            if any(h in blob for h in _VN_HINTS):
                code = _match(c)
                if code:
                    logger.info(f"H&M country resolved to '{code}' for preferred '{preferred}'")
                    await cache_set(cache_key, code, ttl=86400)
                    return code

        for fallback in ("us", "gb", "de", "sg"):
            for c in countries:
                if _match(c) == fallback:
                    logger.warning(
                        f"H&M country '{preferred}' unavailable; using '{fallback}' catalog"
                    )
                    await cache_set(cache_key, fallback, ttl=86400)
                    return fallback

        await cache_set(cache_key, "us", ttl=86400)
        return "us"

    async def list_categories(self, region: str) -> list[dict[str, Any]]:
        cache_key = f"hm:v2:categories:{region}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
        raw = await self._get("categories/list", {"country": region, "lang": "en"})
        flat: list[dict[str, str]] = []
        if isinstance(raw, list):
            for root in raw:
                self._walk_category_tags(root, flat)
        elif isinstance(raw, dict):
            self._walk_category_tags(raw, flat)
        # Prefer new-arrival categories across ladies, men, and kids
        preferred = [
            c for c in flat
            if any(k in c["category_id"].lower() for k in ("newarrivals", "new_arrivals", "viewall"))
        ]
        ladies = [c for c in preferred if "ladies" in c["category_id"].lower()][:6]
        men = [c for c in preferred if c["category_id"].lower().startswith("men")][:4]
        kids = [c for c in preferred if "kids" in c["category_id"].lower()][:2]
        result = ladies + men + kids or preferred or flat
        await cache_set(cache_key, result[:40], ttl=86400)
        return result[:40]

    async def list_products(
        self,
        region: str,
        *,
        category_id: str | None = None,
        page: int = 1,
        sort: str = "NEWEST_FIRST",
        limit: int = 36,
    ) -> list[dict[str, Any]]:
        if not category_id:
            cats = await self.list_categories(region)
            category_id = cats[0]["category_id"] if cats else "ladies_newarrivals_all"
        params: dict[str, Any] = {
            "country": region,
            "lang": "en",
            "page": page,
            "pageSize": limit,
            "categoryId": category_id,
            "sort": sort,
        }
        raw = await self._get("products/v2/list", params)
        return self._unwrap_products(raw)

    async def get_product_detail(self, product_id: str, region: str) -> dict[str, Any]:
        cache_key = f"hm:product:{region}:{product_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
        for path, params in (
            ("products/detail", {"productId": product_id, "country": region, "lang": "en"}),
            ("products/v2/detail", {"id": product_id, "country": region, "lang": "en"}),
        ):
            try:
                raw = await self._get(path, params)
                product = None
                if isinstance(raw, dict):
                    if raw.get("id") or raw.get("productId"):
                        product = raw
                    else:
                        product = raw.get("data") or raw.get("product") or raw
                if isinstance(product, dict):
                    await cache_set(cache_key, product, ttl=3600)
                    return product
            except Exception as exc:
                logger.debug(f"H&M detail {path} failed: {exc}")
        return {}


def dig(obj: Any, *keys: str, default: Any = None) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def product_id(product: dict[str, Any]) -> str:
    return str(
        product.get("id")
        or product.get("productId")
        or product.get("articleId")
        or product.get("code")
        or ""
    ).strip()


def product_name(product: dict[str, Any]) -> str:
    return str(
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or product.get("displayName")
        or "H&M item"
    ).strip()[:255]


def product_image(product: dict[str, Any]) -> str | None:
    for key in ("image", "thumbnail", "mainImage", "productImage", "modelImage"):
        val = product.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    images = product.get("images") or product.get("gallery") or []
    if isinstance(images, list):
        for img in images:
            if isinstance(img, str) and img.startswith("http"):
                return img
            if isinstance(img, dict):
                url = img.get("url") or img.get("src") or img.get("baseUrl")
                if url and str(url).startswith("http"):
                    return str(url)
    return None


def product_price(product: dict[str, Any]) -> tuple[float | None, str]:
    prices = product.get("prices")
    if isinstance(prices, list) and prices:
        block = prices[0]
        if isinstance(block, dict):
            try:
                return float(block.get("price") or block.get("minPrice")), "USD"
            except (TypeError, ValueError):
                pass
    price_block = product.get("price") or product
    if isinstance(price_block, dict):
        amount = price_block.get("value") or price_block.get("amount") or price_block.get("price")
        currency = price_block.get("currency") or price_block.get("currencyCode") or "USD"
    else:
        amount = product.get("price") or product.get("salePrice")
        currency = product.get("currency") or "USD"
    try:
        return float(amount), str(currency)[:8]
    except (TypeError, ValueError):
        return None, "USD"


def product_url(product: dict[str, Any], region: str) -> str | None:
    url = product.get("url") or product.get("link") or product.get("productUrl")
    if url:
        url = str(url)
        if url.startswith("/"):
            return f"https://www2.hm.com{url}"[:1024]
        return url[:1024]
    pid = product_id(product)
    if pid:
        return f"https://www2.hm.com/{region}_en/productpage.{pid}.html"[:1024]
    return None


def category_section(category_id: str) -> str:
    """Map H&M categoryId to catalog section: ladies, men, kids, beauty, home, sportswear."""
    cid = category_id.lower()
    if cid.startswith("men") or "newarrivals_men" in cid or cid.endswith("_men"):
        return "men"
    if cid.startswith("kids") or "kids_" in cid:
        return "kids"
    if cid.startswith("beauty"):
        return "beauty"
    if cid.startswith("home"):
        return "home"
    if cid.startswith("sportswear"):
        return "sportswear"
    if "ladies" in cid or "women" in cid:
        return "ladies"
    return "other"


def product_gender(product: dict[str, Any]) -> str:
    cat_id = str(product.get("_hm_category_id") or "").lower()
    section = category_section(cat_id) if cat_id else ""
    if section == "men":
        return "male"
    if section == "ladies" or section == "beauty":
        return "female"
    if section == "kids":
        if "boys" in cat_id or "boy_" in cat_id:
            return "male"
        if "girls" in cat_id or "girl_" in cat_id:
            return "female"
        return "unisex"

    blob = " ".join(
        str(product.get(k) or "")
        for k in ("gender", "sectionName", "section", "category", "department")
    ).lower()
    if any(x in blob for x in ("men", "male", "man")):
        return "male"
    if any(x in blob for x in ("women", "female", "lady", "ladies")):
        return "female"
    return "unisex"


def product_tags(product: dict[str, Any]) -> list[str]:
    tags: list[str] = ["hm", "hm-api"]
    for key in ("category", "sectionName", "productType", "articleType"):
        val = product.get(key)
        if val:
            tags.append(str(val).lower()[:32])
    colors = product.get("color") or product.get("colors")
    if isinstance(colors, str):
        tags.append(colors.lower()[:32])
    return tags[:12]


def product_colors(product: dict[str, Any]) -> list[str]:
    swatches = product.get("swatches") or []
    if isinstance(swatches, list):
        colors = [str(s.get("colorName")).lower() for s in swatches if isinstance(s, dict) and s.get("colorName")]
        if colors:
            return colors[:6]
    colors = product.get("colors") or product.get("color")
    if isinstance(colors, str):
        return [colors.lower()]
    if isinstance(colors, list):
        return [str(c).lower() for c in colors if c][:6]
    return []


def product_category_label(product: dict[str, Any], fallback: str = "New Arrivals") -> str:
    for key in ("mainCatName", "categoryName", "sectionName", "category"):
        val = product.get(key)
        if val:
            return str(val).strip()
    return fallback


def infer_season_from_product(product: dict[str, Any], month: int | None = None) -> str:
    blob = " ".join(
        str(product.get(k) or "")
        for k in ("name", "title", "category", "collection", "tags")
    ).lower()
    if any(w in blob for w in ("winter", "wool", "coat", "parka", "fleece")):
        return "winter"
    if any(w in blob for w in ("summer", "linen", "swim", "shorts", "tank")):
        return "summer"
    if any(w in blob for w in ("spring", "light jacket")):
        return "spring"
    if any(w in blob for w in ("autumn", "fall")):
        return "autumn"
    if month is None:
        from datetime import datetime, timezone

        month = datetime.now(timezone.utc).month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"
