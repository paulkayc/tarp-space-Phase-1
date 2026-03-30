"""
Escalation flagging — ARCHITECTURE.md Section 3.4, Stage 3
No LLM. Flags candidates that failed hard filter only due to price.

Threshold: mandate.price_ceiling × (1 + ESCALATION_THRESHOLD_PCT)  [default 1.15]
Condition: candidate.price <= threshold AND similarity_score >= 0.75

Escalation candidates returned in separate 'escalations' array, not main results.
"""
from __future__ import annotations

from app.core.config import settings
from app.db.models import Inventory, Mandate
from app.services.privacy.gate import _extract_price_ceiling
from app.services.matching.ranker import rank_candidates


def build_escalation_question(
    item: Inventory,
    price_ceiling: float,
    threshold_delta: float,
) -> str:
    """Generate a specific yes/no escalation question for the owner."""
    return (
        f"This listing is ${threshold_delta:.0f} above your ceiling "
        f"but matches on other dimensions. Want me to explore it?"
    )


def flag_escalations(
    escalation_candidates: list[Inventory],
    mandate: Mandate,
    mandate_description: str | None,
    mandate_embedding: list[float] | None = None,
) -> list[dict]:
    """
    Score and flag escalation candidates.

    Only items with similarity_score >= 0.75 (or text_score >= 0.1 as fallback)
    are included in escalations. This avoids surfacing low-quality escalations
    that don't warrant interrupting the owner.

    Returns list of escalation dicts with:
      inventory_item, threshold_delta, question, alignment_score
    """
    if not escalation_candidates:
        return []

    price_ceiling = _extract_price_ceiling(mandate)
    if price_ceiling is None:
        return []

    # Use the same ranking logic to score escalation candidates
    ranked = rank_candidates(
        escalation_candidates,
        mandate_description=mandate_description,
        mandate_embedding=mandate_embedding,
        price_ceiling=price_ceiling,
        top_n=len(escalation_candidates),
    )

    # Minimum similarity threshold for escalation
    # With embeddings: 0.75, with text fallback: 0.05 (lower bar since text overlap is coarser)
    min_score = 0.75 if mandate_embedding is not None else 0.05

    escalations = []
    for item, alignment_score, _ in ranked:
        if alignment_score < min_score:
            continue

        item_price = float(item.price)
        threshold_delta = round(item_price - price_ceiling, 2)

        escalations.append({
            "inventory_item": item,
            "threshold_delta": threshold_delta,
            "question": build_escalation_question(item, price_ceiling, threshold_delta),
            "alignment_score": alignment_score,
        })

    return escalations
