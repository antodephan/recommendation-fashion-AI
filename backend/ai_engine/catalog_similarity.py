"""Image → catalog similarity (legacy ResNet features + OpenAI vision fallback)."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.core.logger import logger

from ai_engine.embeddings import embed_text
from ai_engine.vector_store import VectorHit, search
from ai_engine.vision import describe_image, embed_image_description

_LEGACY_NEIGHBORS = None
_LEGACY_FILES: list[str] | None = None
_LEGACY_LOADED = False


@dataclass
class CatalogMatch:
    catalog_id: str | None
    outfit_id: str | None
    score: float
    source: str


def _legacy_paths() -> tuple[Path, Path] | None:
    base = Path(settings.FASHION_LEGACY_DIR)
    features = base / "model" / "feature_data.pkl"
    names = base / "model" / "file_names.pkl"
    if features.is_file() and names.is_file():
        return features, names
    return None


def _load_legacy_knn() -> bool:
    """Lazy-load pre-trained ResNet feature index from the Flask project."""
    global _LEGACY_NEIGHBORS, _LEGACY_FILES, _LEGACY_LOADED
    if _LEGACY_LOADED:
        return _LEGACY_NEIGHBORS is not None

    _LEGACY_LOADED = True
    paths = _legacy_paths()
    if not paths:
        return False

    try:
        from sklearn.neighbors import NearestNeighbors
    except ImportError:
        logger.warning("scikit-learn not installed; legacy image KNN disabled")
        return False

    features_path, names_path = paths
    try:
        with open(features_path, "rb") as f:
            features = pickle.load(f)
        with open(names_path, "rb") as f:
            files = pickle.load(f)
    except Exception as exc:
        logger.warning(f"Failed to load legacy features: {exc}")
        return False

    if len(features) == 0 or len(files) == 0:
        return False

    _LEGACY_FILES = [str(x) for x in files]
    _LEGACY_NEIGHBORS = NearestNeighbors(
        n_neighbors=min(80, len(_LEGACY_FILES)),
        metric="cosine",
        algorithm="brute",
    )
    _LEGACY_NEIGHBORS.fit(features)
    logger.info(f"Legacy image KNN ready ({len(_LEGACY_FILES)} vectors)")
    return True


def _extract_upload_feature(image_bytes: bytes) -> np.ndarray | None:
    """Extract ResNet feature for an upload (requires torch)."""
    try:
        import torch
        from io import BytesIO
        from PIL import Image
        from torchvision import models, transforms
    except ImportError:
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    weights = models.ResNet50_Weights.DEFAULT
    backbone = models.resnet50(weights=weights)
    model = torch.nn.Sequential(*list(backbone.children())[:-1]).to(device)
    model.eval()

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model(tensor).squeeze().detach().cpu().numpy().astype(np.float32)
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm


def legacy_knn_catalog_ids(image_bytes: bytes, *, top_k: int = 25) -> list[tuple[str, float]]:
    """Return catalog ids from pre-trained feature_data.pkl (Flask dataset)."""
    if not _load_legacy_knn() or _LEGACY_NEIGHBORS is None or _LEGACY_FILES is None:
        return []

    feature = _extract_upload_feature(image_bytes)
    if feature is None:
        return []

    distances, indices = _LEGACY_NEIGHBORS.kneighbors(feature.reshape(1, -1), n_neighbors=top_k + 1)
    results: list[tuple[str, float]] = []
    for idx, dist in zip(indices[0][1:], distances[0][1:]):
        filename = _LEGACY_FILES[int(idx)]
        catalog_id = Path(filename).stem
        score = max(0.0, 1.0 - float(dist) / 2.0)
        results.append((catalog_id, score))
    return results


async def vision_vector_search(image_bytes: bytes, *, top_k: int = 25) -> list[VectorHit]:
    """OpenAI vision description → embedding → Qdrant outfit search."""
    description = await describe_image(image_bytes)
    vector = await embed_image_description(description)
    return await search(settings.QDRANT_COLLECTION_OUTFITS, vector, top_k=top_k)


async def describe_image_for_query(image_bytes: bytes) -> str:
    """Text summary of an inspiration image to enrich the LLM query."""
    description = await describe_image(image_bytes)
    parts: list[str] = []
    if description.get("overall_style"):
        parts.append(f"style {description['overall_style']}")
    if description.get("dominant_colors"):
        parts.append(f"colors {', '.join(description['dominant_colors'][:5])}")
    if description.get("suggested_tags"):
        parts.append(f"tags {', '.join(description['suggested_tags'][:8])}")
    for item in (description.get("items") or [])[:4]:
        bits = [item.get("category"), item.get("color"), item.get("style")]
        parts.append(" ".join(b for b in bits if b))
    return ". ".join(parts) if parts else ""


async def find_image_matches(
    image_bytes: bytes,
    *,
    top_k: int = 25,
) -> tuple[list[CatalogMatch], dict[str, Any]]:
    """Combine legacy KNN + vision vector search for hybrid recommendations."""
    meta: dict[str, Any] = {"legacy_knn": False, "vision_search": False}
    matches: list[CatalogMatch] = []

    legacy = legacy_knn_catalog_ids(image_bytes, top_k=top_k)
    if legacy:
        meta["legacy_knn"] = True
        for catalog_id, score in legacy:
            matches.append(
                CatalogMatch(catalog_id=catalog_id, outfit_id=None, score=0.75 * score, source="legacy_knn")
            )

    hits = await vision_vector_search(image_bytes, top_k=top_k)
    if hits:
        meta["vision_search"] = True
        for h in hits:
            catalog_id = (h.payload or {}).get("catalog_id")
            matches.append(
                CatalogMatch(
                    catalog_id=str(catalog_id) if catalog_id else None,
                    outfit_id=h.id,
                    score=0.65 * h.score,
                    source="vision_vector",
                )
            )

    # Deduplicate by outfit_id / catalog_id keeping best score
    best: dict[str, CatalogMatch] = {}
    for m in matches:
        key = m.outfit_id or f"cat:{m.catalog_id}"
        if not key:
            continue
        prev = best.get(key)
        if prev is None or m.score > prev.score:
            best[key] = m

    return list(best.values()), meta
