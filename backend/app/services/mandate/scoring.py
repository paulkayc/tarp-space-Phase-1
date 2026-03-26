"""
Mandate completeness scoring.
"""
from __future__ import annotations

from typing import Any


def _get_value(mandate: Any, key: str):
    if isinstance(mandate, dict):
        return mandate.get(key)
    return getattr(mandate, key, None)


def _has_price_range(negotiation_range: Any) -> bool:
    if not isinstance(negotiation_range, list):
        return False
    for entry in negotiation_range:
        if not isinstance(entry, dict):
            continue
        if entry.get("dimension") != "price":
            continue
        if entry.get("min") is not None or entry.get("max") is not None:
            return True
    return False


def _has_hard_constraint(hard_constraints: Any, field_name: str) -> bool:
    if not isinstance(hard_constraints, list):
        return False
    for entry in hard_constraints:
        if not isinstance(entry, dict):
            continue
        if entry.get("field") == field_name and entry.get("value"):
            return True
    return False


def compute_completeness_score(mandate: Any) -> float:
    intent_type = _get_value(mandate, "intent_type")
    vertical = _get_value(mandate, "vertical")
    category = _get_value(mandate, "category")
    negotiation_range = _get_value(mandate, "negotiation_range") or []
    hard_constraints = _get_value(mandate, "hard_constraints") or []
    soft_preferences = _get_value(mandate, "soft_preferences") or []
    dealbreakers = _get_value(mandate, "dealbreakers") or []

    has_triplet = bool(intent_type and vertical and category)
    has_price = _has_price_range(negotiation_range)
    has_location = _has_hard_constraint(hard_constraints, "location")
    has_condition = _has_hard_constraint(hard_constraints, "condition")
    has_timing = _has_hard_constraint(hard_constraints, "timing")
    has_soft_prefs = isinstance(soft_preferences, list) and len(soft_preferences) > 0
    has_meaningful_data = any(
        [has_triplet, has_price, has_location, has_condition, has_timing, has_soft_prefs, len(dealbreakers) > 0]
    )
    if not has_meaningful_data:
        return 0.0

    score = 0.0
    score += 0.35 if has_triplet else 0.0
    score += 0.20 if has_price else 0.0
    score += 0.15 if has_location else 0.0
    score += 0.075 if has_condition else 0.0
    score += 0.075 if has_timing else 0.0
    score += 0.10 if has_soft_prefs else 0.0
    score += 0.05
    return round(min(score, 1.0), 3)
