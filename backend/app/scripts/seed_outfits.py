"""Seed an initial outfit catalog and index it in Qdrant."""

from __future__ import annotations

from sqlalchemy import select

from app.core.logger import logger
from app.database import AsyncSessionLocal
from app.models.outfit import Outfit, OutfitItem

from ai_engine.catalog_index import index_outfits_to_qdrant

SEED_OUTFITS = [
    {
        "name": "Minimalist Monochrome",
        "description": "Crisp black oversized blazer with white wide-leg trousers and chunky loafers — clean and editorial.",
        "image_url": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800",
        "style": "minimalist",
        "season": "all",
        "gender": "unisex",
        "occasion": "work",
        "colors": ["black", "white"],
        "materials": ["wool", "leather"],
        "tags": ["editorial", "monochrome", "office"],
        "brand": "Studio Nicholson",
        "price": 480.0,
        "rating": 4.6,
        "popularity": 980,
        "items": [
            {"category": "top", "name": "Oversized blazer", "color": "black", "material": "wool"},
            {"category": "bottom", "name": "Wide-leg trousers", "color": "white"},
            {"category": "shoes", "name": "Chunky loafers", "color": "black"},
        ],
    },
    {
        "name": "Cozy Autumn Layers",
        "description": "Cream cable-knit sweater, camel trench, dark wash jeans and clean white sneakers.",
        "image_url": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800",
        "style": "casual",
        "season": "autumn",
        "gender": "female",
        "occasion": "casual",
        "colors": ["cream", "camel", "blue"],
        "materials": ["cotton", "wool", "denim"],
        "tags": ["cozy", "layers", "weekend"],
        "brand": "Everlane",
        "price": 320.0,
        "rating": 4.8,
        "popularity": 1320,
        "items": [
            {"category": "top", "name": "Cable-knit sweater", "color": "cream", "material": "wool"},
            {"category": "outerwear", "name": "Camel trench coat"},
            {"category": "bottom", "name": "Dark wash jeans", "color": "blue", "material": "denim"},
            {"category": "shoes", "name": "White sneakers"},
        ],
    },
    {
        "name": "Streetwear Statement",
        "description": "Graphic hoodie, baggy cargo pants, retro sneakers — confident and energetic.",
        "image_url": "https://images.unsplash.com/photo-1521223890158-f9f7c3d5d504?w=800",
        "style": "streetwear",
        "season": "spring",
        "gender": "male",
        "occasion": "casual",
        "colors": ["navy", "olive", "white"],
        "materials": ["cotton", "nylon"],
        "tags": ["streetwear", "y2k", "bold"],
        "brand": "Carhartt",
        "price": 260.0,
        "rating": 4.4,
        "popularity": 1180,
        "items": [
            {"category": "top", "name": "Graphic hoodie", "color": "navy"},
            {"category": "bottom", "name": "Cargo pants", "color": "olive"},
            {"category": "shoes", "name": "Retro sneakers", "color": "white"},
        ],
    },
    {
        "name": "Summer Linen Look",
        "description": "Beige linen shirt, sand chinos and woven loafers — breezy and refined.",
        "image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=800",
        "style": "smart-casual",
        "season": "summer",
        "gender": "male",
        "occasion": "weekend",
        "colors": ["beige", "sand"],
        "materials": ["linen", "cotton"],
        "tags": ["linen", "summer", "vacation"],
        "brand": "COS",
        "price": 220.0,
        "rating": 4.5,
        "popularity": 870,
        "items": [
            {"category": "top", "name": "Linen shirt", "color": "beige", "material": "linen"},
            {"category": "bottom", "name": "Sand chinos", "color": "sand"},
            {"category": "shoes", "name": "Woven loafers"},
        ],
    },
    {
        "name": "Evening Power Suit",
        "description": "Tailored black double-breasted suit with silk shell and minimalist heels.",
        "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800",
        "style": "formal",
        "season": "all",
        "gender": "female",
        "occasion": "evening",
        "colors": ["black"],
        "materials": ["wool", "silk"],
        "tags": ["powerful", "evening", "tailored"],
        "brand": "The Frankie Shop",
        "price": 620.0,
        "rating": 4.9,
        "popularity": 1500,
        "items": [
            {"category": "top", "name": "Double-breasted blazer", "color": "black"},
            {"category": "bottom", "name": "Tailored trousers", "color": "black"},
            {"category": "shoes", "name": "Minimalist heels", "color": "black"},
        ],
    },
    {
        "name": "Vintage Denim & Tee",
        "description": "Plain white tee, high-rise vintage Levi’s and worn-in leather boots.",
        "image_url": "https://images.unsplash.com/photo-1495121605193-b116b5b9c5fe?w=800",
        "style": "vintage",
        "season": "all",
        "gender": "unisex",
        "occasion": "casual",
        "colors": ["white", "blue", "brown"],
        "materials": ["cotton", "denim", "leather"],
        "tags": ["vintage", "denim", "americana"],
        "brand": "Levi's",
        "price": 180.0,
        "rating": 4.7,
        "popularity": 1750,
        "items": [
            {"category": "top", "name": "Plain white tee", "color": "white"},
            {"category": "bottom", "name": "Vintage 501 jeans", "color": "blue"},
            {"category": "shoes", "name": "Leather boots", "color": "brown"},
        ],
    },
    {
        "name": "Modern Athleisure",
        "description": "Performance hoodie, slim joggers and minimalist running shoes — sleek travel-day look.",
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800",
        "style": "athleisure",
        "season": "all",
        "gender": "unisex",
        "occasion": "travel",
        "colors": ["grey", "black"],
        "materials": ["technical", "cotton"],
        "tags": ["athleisure", "comfort", "travel"],
        "brand": "Lululemon",
        "price": 280.0,
        "rating": 4.6,
        "popularity": 1090,
        "items": [
            {"category": "top", "name": "Performance hoodie", "color": "grey"},
            {"category": "bottom", "name": "Slim joggers", "color": "black"},
            {"category": "shoes", "name": "Minimalist runners"},
        ],
    },
    {
        "name": "Bohemian Festival",
        "description": "Flowy floral midi dress, layered necklaces and suede ankle boots.",
        "image_url": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=800",
        "style": "bohemian",
        "season": "spring",
        "gender": "female",
        "occasion": "festival",
        "colors": ["rust", "ivory"],
        "materials": ["cotton", "suede"],
        "tags": ["boho", "festival", "floral"],
        "brand": "Free People",
        "price": 240.0,
        "rating": 4.5,
        "popularity": 870,
        "items": [
            {"category": "dress", "name": "Floral midi dress", "color": "rust"},
            {"category": "accessory", "name": "Layered necklaces"},
            {"category": "shoes", "name": "Suede ankle boots"},
        ],
    },
]


async def seed_outfits() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Outfit).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("Outfits already seeded; skipping.")
            return

        outfits: list[Outfit] = []
        for spec in SEED_OUTFITS:
            data = dict(spec)
            items_spec = data.pop("items", [])
            outfit = Outfit(**data)
            outfit.items = [OutfitItem(**it) for it in items_spec]
            db.add(outfit)
            outfits.append(outfit)
        await db.commit()
        for o in outfits:
            await db.refresh(o)

        logger.info(f"Inserted {len(outfits)} outfits, indexing in Qdrant…")
        await index_outfits_to_qdrant(outfits)
        logger.info("Outfits indexed in Qdrant ✅")
