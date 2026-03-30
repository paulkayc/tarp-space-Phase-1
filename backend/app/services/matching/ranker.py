"""
Semantic ranker — ARCHITECTURE.md Section 3.4, Stage 2
No LLM. pgvector cosine similarity against pre-computed listing embeddings.

alignment_score = similarity_score × (1 + trust_weight × 0.3)
trust_weight = 0.0 in Phase 1 (no live trust graph).

When inventory items have pre-computed embeddings, this function uses
cosine similarity. When embeddings are absent (tests, seed-less environments),
falls back to Jaccard token overlap on description strings.
"""
from __future__ import annotations

import math

from app.db.models import Inventory


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_similarity(text_a: str, text_b: str) -> float:
    """Jaccard token overlap — fallback when embeddings are unavailable."""
    if not text_a or not text_b:
        return 0.0
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _determine_matched_dimensions(
    item: Inventory,
    mandate_description: str | None,
    price_ceiling: float | None,
) -> list[str]:
    """Identify which mandate dimensions this item matches on."""
    matched: list[str] = []

    # Category always considered matched if item made it through filter
    matched.append("category")

    # Vertical
    matched.append("vertical")

    # Price
    if price_ceiling is not None and float(item.price) <= price_ceiling:
        matched.append("price")

    # Location
    if item.location_raw:
        matched.append("location")

    # Metadata-based soft dimensions
    meta = item.metadata_json or {}
    if meta.get("condition"):
        matched.append("condition")
    if meta.get("style") or meta.get("aesthetic"):
        matched.append("style")

    return matched


def rank_candidates(
    candidates: list[Inventory],
    mandate_description: str | None,
    mandate_embedding: list[float] | None = None,
    price_ceiling: float | None = None,
    top_n: int = 5,
) -> list[tuple[Inventory, float, list[str]]]:
    """
    Rank candidates by alignment score.

    Phase 1: trust_weight = 0.0, so:
      alignment_score = similarity_score * (1 + 0.0 * 0.3) = similarity_score

    Returns list of (inventory_item, alignment_score, matched_dimensions)
    sorted descending by alignment_score, limited to top_n.
    """
    if not candidates:
        return []

    results: list[tuple[Inventory, float, list[str]]] = []

    for item in candidates:
        # Compute similarity score
        if mandate_embedding is not None and item.embedding is not None:
            # Use real cosine similarity when both embeddings are available
            item_emb = list(item.embedding)
            similarity_score = _cosine_similarity(mandate_embedding, item_emb)
        else:
            # Fallback: Jaccard text overlap on descriptions
            similarity_score = _text_similarity(
                mandate_description or "",
                item.description or "",
            )

        # Phase 1: trust_weight = 0.0
        trust_weight = 0.0
        alignment_score = similarity_score * (1.0 + trust_weight * 0.3)

        matched_dims = _determine_matched_dimensions(item, mandate_description, price_ceiling)
        results.append((item, round(alignment_score, 4), matched_dims))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_n]
